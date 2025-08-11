'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowLeft, CreditCard, DollarSign, TrendingUp, Settings, History, Download, Shield } from 'lucide-react';
import { AuthGuard } from '@/components/auth-guard';
import toast from 'react-hot-toast';

function PaymentPageContent() {
  const [selectedPlan, setSelectedPlan] = useState('pro');
  const [isProcessing, setIsProcessing] = useState(false);
  const router = useRouter();

  const plans = [
    {
      id: 'free',
      name: 'FREE TIER',
      price: '$0',
      period: 'month',
      features: [
        '5 video credits per month',
        'Basic AI features',
        '720p output',
        'Community support'
      ],
      limits: {
        videoCredits: 5,
        magicCommands: 10,
        storage: '1GB',
        priority: 'Low'
      }
    },
    {
      id: 'pro',
      name: 'PRO PLAN',
      price: '$29',
      period: 'month',
      features: [
        '50 video credits per month',
        'Advanced AI features',
        '4K output',
        'Priority support',
        'Magic commands',
        'Content repurposing'
      ],
      limits: {
        videoCredits: 50,
        magicCommands: 100,
        storage: '10GB',
        priority: 'High'
      }
    },
    {
      id: 'enterprise',
      name: 'ENTERPRISE',
      price: '$99',
      period: 'month',
      features: [
        'Unlimited video credits',
        'All AI features',
        '8K output',
        '24/7 support',
        'Custom integrations',
        'White-label options'
      ],
      limits: {
        videoCredits: -1, // Unlimited
        magicCommands: -1, // Unlimited
        storage: '100GB',
        priority: 'Highest'
      }
    }
  ];

  // Removed fake usage statistics - these should come from real API data

  const handleUpgrade = async () => {
    setIsProcessing(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      toast.success('SUBSCRIPTION UPGRADED SUCCESSFULLY');
    } catch (error) {
      toast.error('UPGRADE FAILED');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDowngrade = async () => {
    setIsProcessing(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      toast.success('SUBSCRIPTION DOWNGRADED SUCCESSFULLY');
    } catch (error) {
      toast.error('DOWNGRADE FAILED');
    } finally {
      setIsProcessing(false);
    }
  };

  const currentPlan = plans.find(p => p.id === selectedPlan);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" size="sm" onClick={() => router.push('/')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            BACK TO TERMINAL
          </Button>
          <div>
            <h1 className="alien-league-title-large">BILLING SYSTEM MODULE</h1>
            <p className="terminal-text-dim">Manage subscription and usage</p>
          </div>
        </div>
        <div className="flex space-x-2">
          <Button variant="outline" size="sm">
            <History className="mr-2 h-4 w-4" />
            INVOICES
          </Button>
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" />
            SETTINGS
          </Button>
        </div>
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="alien-league-title">BILLING SYSTEM STATUS</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="data-display">
              <span className="data-label">PAYMENT PROCESSOR:</span>
              <span className="data-value ml-2">STRIPE</span>
            </div>
            <div className="data-display">
              <span className="data-label">BILLING CYCLE:</span>
              <span className="data-value ml-2">MONTHLY</span>
            </div>
            <div className="data-display">
              <span className="data-label">NEXT BILLING:</span>
              <span className="data-value ml-2">2024-02-01</span>
            </div>
            <div className="data-display">
              <span className="data-label">STATUS:</span>
              <span className="data-value ml-2">ACTIVE</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Current Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="alien-league-title">CURRENT USAGE</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="terminal-text-dim">Usage statistics will be loaded from your account data</p>
            <p className="terminal-text-dim text-sm mt-2">Connect to API to view real usage metrics</p>
          </div>
        </CardContent>
      </Card>

      {/* Plans */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {plans.map((plan) => (
          <Card 
            key={plan.id} 
            className={`cursor-pointer transition-colors ${
              selectedPlan === plan.id ? 'border-green-400' : ''
            }`}
            onClick={() => setSelectedPlan(plan.id)}
          >
            <CardHeader>
              <CardTitle className="alien-league-title text-center">{plan.name}</CardTitle>
              <div className="text-center">
                <span className="terminal-text-bold text-2xl">{plan.price}</span>
                <span className="terminal-text-dim">/{plan.period}</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {plan.features.map((feature, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text text-sm">{feature}</span>
                  </div>
                ))}
              </div>
              
              <div className="border border-green-500 p-3 space-y-2">
                <div className="data-display">
                  <span className="data-label">VIDEO CREDITS:</span>
                  <span className="data-value ml-2">
                    {plan.limits.videoCredits === -1 ? 'UNLIMITED' : plan.limits.videoCredits}
                  </span>
                </div>
                <div className="data-display">
                  <span className="data-label">MAGIC COMMANDS:</span>
                  <span className="data-value ml-2">
                    {plan.limits.magicCommands === -1 ? 'UNLIMITED' : plan.limits.magicCommands}
                  </span>
                </div>
                <div className="data-display">
                  <span className="data-label">STORAGE:</span>
                  <span className="data-value ml-2">{plan.limits.storage}</span>
                </div>
                <div className="data-display">
                  <span className="data-label">PRIORITY:</span>
                  <span className="data-value ml-2">{plan.limits.priority}</span>
                </div>
              </div>

              {selectedPlan === plan.id ? (
                <div className="space-y-2">
                  {plan.id === 'free' ? (
                    <Button 
                      onClick={handleDowngrade}
                      disabled={isProcessing}
                      variant="outline"
                      className="w-full"
                    >
                      {isProcessing ? (
                        <>
                          <div className="spinner mr-2" />
                          PROCESSING...
                        </>
                      ) : (
                        'CURRENT PLAN'
                      )}
                    </Button>
                  ) : (
                    <Button 
                      onClick={handleUpgrade}
                      disabled={isProcessing}
                      className="w-full"
                    >
                      {isProcessing ? (
                        <>
                          <div className="spinner mr-2" />
                          PROCESSING...
                        </>
                      ) : (
                        <>
                          <CreditCard className="mr-2 h-4 w-4" />
                          {plan.id === 'pro' ? 'UPGRADE TO PRO' : 'UPGRADE TO ENTERPRISE'}
                        </>
                      )}
                    </Button>
                  )}
                </div>
              ) : (
                <Button 
                  variant="outline"
                  className="w-full"
                  onClick={() => setSelectedPlan(plan.id)}
                >
                  SELECT PLAN
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Billing History */}
      <Card>
        <CardHeader>
          <CardTitle className="alien-league-title">BILLING HISTORY</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 border border-green-500">
              <div>
                <div className="terminal-text-bold">January 2024</div>
                <div className="terminal-text-dim text-sm">Pro Plan - Monthly</div>
              </div>
              <div className="text-right">
                <div className="terminal-text-bold">$29.00</div>
                <div className="terminal-text-dim text-sm">Paid</div>
              </div>
            </div>
            <div className="flex items-center justify-between p-3 border border-green-500">
              <div>
                <div className="terminal-text-bold">December 2023</div>
                <div className="terminal-text-dim text-sm">Pro Plan - Monthly</div>
              </div>
              <div className="text-right">
                <div className="terminal-text-bold">$29.00</div>
                <div className="terminal-text-dim text-sm">Paid</div>
              </div>
            </div>
            <div className="flex items-center justify-between p-3 border border-green-500">
              <div>
                <div className="terminal-text-bold">November 2023</div>
                <div className="terminal-text-dim text-sm">Free Plan</div>
              </div>
              <div className="text-right">
                <div className="terminal-text-bold">$0.00</div>
                <div className="terminal-text-dim text-sm">Free</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="border-t border-green-500 pt-4">
        <div className="flex justify-between items-center text-xs text-green-600">
          <span className="font-digital">BILLING SYSTEM MODULE v2.1.0</span>
            <span className="font-digital">SECURE PAYMENT PROCESSING</span>
            <span className="font-digital">ALL TRANSACTIONS SECURE</span>
        </div>
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <AuthGuard>
      <PaymentPageContent />
    </AuthGuard>
  );
}
