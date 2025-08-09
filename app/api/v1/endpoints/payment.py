from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.services.payment import payment_service
from app.core.config import settings
import logging
import stripe

logger = logging.getLogger(__name__)
router = APIRouter()

class CreateCheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str

@router.get("/plans")
def get_pricing_plans():
    """Get available pricing plans"""
    return {"plans": payment_service.plans}

@router.get("/usage")
def get_user_usage(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get current user's plan and usage"""
    return payment_service.get_user_plan(db, current_user.id)

@router.post("/create-checkout")
def create_checkout_session(
    request: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Create Stripe checkout session for subscription"""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=501,
            detail="Payment processing not configured"
        )
    
    if request.plan not in payment_service.plans:
        raise HTTPException(
            status_code=400,
            detail="Invalid plan selected"
        )
    
    if request.plan == "free":
        raise HTTPException(
            status_code=400,
            detail="Cannot create checkout for free plan"
        )
    
    checkout_url = payment_service.create_checkout_session(
        plan=request.plan,
        user_email=current_user.email,
        success_url=request.success_url,
        cancel_url=request.cancel_url
    )
    
    if not checkout_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to create checkout session"
        )
    
    return {"checkout_url": checkout_url}

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=501,
            detail="Webhook processing not configured"
        )
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    if not sig_header:
        raise HTTPException(
            status_code=400,
            detail="Missing stripe-signature header"
        )
    
    success = payment_service.handle_webhook(
        payload.decode('utf-8'),
        sig_header
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook"
        )
    
    return {"status": "success"}

@router.post("/check-limits")
def check_usage_limits(
    operation: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Check if user can perform operation based on their plan"""
    can_proceed = payment_service.check_usage_limits(db, current_user.id, operation)
    
    if not can_proceed:
        user_plan = payment_service.get_user_plan(db, current_user.id)
        if operation == "video_processing":
            detail = f"Video processing limit reached. You have {user_plan['video_credits_remaining']} credits remaining."
        elif operation == "magic_command":
            detail = f"Magic command limit reached. You have {user_plan['magic_commands_remaining']} commands remaining."
        else:
            detail = "Usage limit reached for this operation."
        
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=detail
        )
    
    return {"allowed": True}