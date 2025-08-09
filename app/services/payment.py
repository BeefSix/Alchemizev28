import stripe
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.db import crud, models
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:
    """Basic payment service for MVP"""
    
    def __init__(self):
        self.plans = {
            "free": {
                "name": "Free",
                "price": 0,
                "video_credits": 3,
                "magic_commands": 10,
                "features": ["Basic video processing", "Standard captions", "3 videos/month"]
            },
            "pro": {
                "name": "Pro",
                "price": 19.99,
                "stripe_price_id": "price_pro_monthly",  # Replace with actual Stripe price ID
                "video_credits": 50,
                "magic_commands": 500,
                "features": ["HD video processing", "Advanced captions", "50 videos/month", "Magic Editor", "Priority support"]
            },
            "enterprise": {
                "name": "Enterprise",
                "price": 99.99,
                "stripe_price_id": "price_enterprise_monthly",  # Replace with actual Stripe price ID
                "video_credits": 500,
                "magic_commands": 5000,
                "features": ["4K video processing", "Custom branding", "Unlimited videos", "API access", "Dedicated support"]
            }
        }
    
    def get_user_plan(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Get user's current plan and usage"""
        user = crud.get_user(db, user_id=user_id)
        if not user:
            return {"plan": "free", "credits_remaining": 0}
        
        # Get current month usage
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Count video jobs this month
        video_jobs_count = db.query(models.Job).filter(
            models.Job.user_id == user_id,
            models.Job.created_at >= current_month_start,
            models.Job.job_type == "video_processing"
        ).count()
        
        # Count magic commands this month
        magic_usage = db.query(models.UsageLog).filter(
            models.UsageLog.user_id == user_id,
            models.UsageLog.timestamp >= current_month_start,
            models.UsageLog.operation == "magic_command"
        ).count()
        
        # Determine user plan (default to free for MVP)
        user_plan = getattr(user, 'subscription_plan', 'free') or 'free'
        plan_info = self.plans.get(user_plan, self.plans['free'])
        
        return {
            "plan": user_plan,
            "plan_info": plan_info,
            "video_credits_used": video_jobs_count,
            "video_credits_remaining": max(0, plan_info['video_credits'] - video_jobs_count),
            "magic_commands_used": magic_usage,
            "magic_commands_remaining": max(0, plan_info['magic_commands'] - magic_usage)
        }
    
    def check_usage_limits(self, db: Session, user_id: int, operation: str) -> bool:
        """Check if user can perform operation based on their plan"""
        user_plan = self.get_user_plan(db, user_id)
        
        if operation == "video_processing":
            return user_plan['video_credits_remaining'] > 0
        elif operation == "magic_command":
            return user_plan['magic_commands_remaining'] > 0
        
        return True
    
    def create_checkout_session(self, plan: str, user_email: str, success_url: str, cancel_url: str) -> Optional[str]:
        """Create Stripe checkout session"""
        if not settings.STRIPE_SECRET_KEY:
            logger.warning("Stripe not configured")
            return None
        
        if plan not in self.plans or plan == "free":
            return None
        
        plan_info = self.plans[plan]
        
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': plan_info['stripe_price_id'],
                    'quantity': 1,
                }],
                mode='subscription',
                customer_email=user_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'plan': plan,
                    'user_email': user_email
                }
            )
            return session.url
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            return None
    
    def handle_webhook(self, payload: str, sig_header: str) -> bool:
        """Handle Stripe webhook events"""
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.warning("Stripe webhook secret not configured")
            return False
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("Invalid payload")
            return False
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature")
            return False
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            self._handle_successful_payment(session)
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            self._handle_subscription_renewal(invoice)
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            self._handle_subscription_cancellation(subscription)
        
        return True
    
    def _handle_successful_payment(self, session: Dict[str, Any]):
        """Handle successful payment"""
        try:
            user_email = session.get('customer_email')
            plan = session.get('metadata', {}).get('plan')
            
            logger.info(f"Payment successful for user, plan: {plan}")
            
            # Update user subscription in database
            from app.db.base import get_db
            from app.db import crud
            
            db = next(get_db())
            try:
                user = crud.get_user_by_email(db, email=user_email)
                if user:
                    # Update user's subscription plan
                    user.subscription_plan = plan
                    user.subscription_status = 'active'
                    user.subscription_updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Updated subscription for user {user_email} to {plan}")
                else:
                    logger.error(f"User not found for email: {user_email}")
            except Exception as e:
                logger.error(f"Database error updating subscription: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling payment success: {e}")
    
    def _handle_subscription_renewal(self, invoice: Dict[str, Any]):
        """Handle subscription renewal"""
        try:
            subscription_id = invoice.get('subscription')
            customer_email = invoice.get('customer_email')
            
            logger.info(f"Subscription renewed: {invoice.get('id')}")
            
            # Reset user credits for new billing period
            from app.db.base import get_db
            from app.db import crud
            
            db = next(get_db())
            try:
                user = crud.get_user_by_email(db, email=customer_email)
                if user:
                    # Reset monthly usage counters
                    user.videos_processed_this_month = 0
                    user.last_billing_reset = datetime.utcnow()
                    db.commit()
                    logger.info("Reset billing cycle for user")
                else:
                    logger.error("User not found for renewal")
            except Exception as e:
                logger.error(f"Database error handling renewal: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling subscription renewal: {e}")
    
    def _handle_subscription_cancellation(self, subscription: Dict[str, Any]):
        """Handle subscription cancellation"""
        try:
            customer_email = subscription.get('customer_email')
            
            logger.info(f"Subscription cancelled: {subscription.get('id')}")
            
            # Downgrade user to free plan
            from app.db.base import get_db
            from app.db import crud
            
            db = next(get_db())
            try:
                user = crud.get_user_by_email(db, email=customer_email)
                if user:
                    # Downgrade to free plan
                    user.subscription_plan = 'free'
                    user.subscription_status = 'cancelled'
                    user.subscription_cancelled_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Downgraded user {customer_email} to free plan")
                else:
                    logger.error(f"User not found for cancellation: {customer_email}")
            except Exception as e:
                logger.error(f"Database error handling cancellation: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling subscription cancellation: {e}")

# Global instance
payment_service = PaymentService()