# utils/budget_helpers.py
"""
Helper functions for budget validation and tier assignment
"""
import logging

logger = logging.getLogger(__name__)

def validate_budget_amount(amount: float) -> dict:
    """
    Validate budget amount and determine appropriate tier
    
    Args:
        amount: Budget amount in USD
    
    Returns:
        dict with validation results and tier info
    """
    try:
        from config import CUSTOM_BUDGET_RECOMMENDATIONS
        
        # Minimum budget check
        if amount < 100:
            return {
                'valid': False,
                'message': '❌ Minimum budget is $100. Please enter a higher amount.',
                'min_amount': 100
            }
        
        # Determine tier based on amount
        tier = None
        for tier_name, tier_info in CUSTOM_BUDGET_RECOMMENDATIONS.items():
            if tier_info['min'] <= amount <= tier_info['max']:
                tier = tier_name
                break
        
        # If amount exceeds highest tier, assign to enterprise
        if not tier:
            highest_tier = list(CUSTOM_BUDGET_RECOMMENDATIONS.keys())[-1]
            if amount > CUSTOM_BUDGET_RECOMMENDATIONS[highest_tier]['max']:
                tier = highest_tier
        
        return {
            'valid': True,
            'amount': amount,
            'tier': tier,
            'message': f'✅ Budget of ${amount:.2f} is valid.',
            'tier_description': CUSTOM_BUDGET_RECOMMENDATIONS[tier]['description'],
            'examples': CUSTOM_BUDGET_RECOMMENDATIONS[tier]['examples']
        }
        
    except ImportError:
        # Fallback if config doesn't exist
        if amount < 100:
            return {
                'valid': False,
                'message': '❌ Minimum budget is $100. Please enter a higher amount.',
                'min_amount': 100
            }
        
        # Simple tier determination
        if amount < 299:
            tier = 'basic'
        elif amount < 799:
            tier = 'standard'
        elif amount < 1499:
            tier = 'premium'
        else:
            tier = 'enterprise'
        
        return {
            'valid': True,
            'amount': amount,
            'tier': tier,
            'message': f'✅ Budget of ${amount:.2f} is valid.',
            'tier_description': '',
            'examples': []
        }
    except Exception as e:
        logger.error(f"Error in validate_budget_amount: {e}")
        return {
            'valid': False,
            'message': '❌ Error validating budget. Please try again.'
        }

def calculate_deposit_amount(amount: float, deposit_percentage: float = 0.2) -> dict:
    """
    Calculate deposit amount and breakdown
    
    Args:
        amount: Total budget amount
        deposit_percentage: Deposit percentage (default 20%)
    
    Returns:
        dict with deposit calculations
    """
    try:
        deposit = amount * deposit_percentage
        remaining = amount - deposit
        
        return {
            'total_amount': amount,
            'deposit_percentage': deposit_percentage * 100,
            'deposit_amount': deposit,
            'remaining_amount': remaining,
            'breakdown': f"Total: ${amount:.2f}\nDeposit ({deposit_percentage*100:.0f}%): ${deposit:.2f}\nRemaining: ${remaining:.2f}"
        }
    except Exception as e:
        logger.error(f"Error in calculate_deposit_amount: {e}")
        return {
            'total_amount': amount,
            'deposit_amount': amount * 0.2,
            'remaining_amount': amount * 0.8,
            'error': str(e)
        }

def get_delivery_time_for_tier(tier: str) -> str:
    """
    Get estimated delivery time for a tier
    
    Args:
        tier: Budget tier (basic, standard, premium, enterprise)
    
    Returns:
        Delivery time estimate
    """
    try:
        from config import CUSTOM_BOT_DELIVERY
        return CUSTOM_BOT_DELIVERY.get(tier, '2-4 weeks')
    except ImportError:
        # Default delivery times if config not available
        delivery_times = {
            'basic': '2-3 weeks',
            'standard': '3-4 weeks',
            'premium': '4-6 weeks',
            'enterprise': '6-8 weeks'
        }
        return delivery_times.get(tier, '2-4 weeks')
    except Exception as e:
        logger.error(f"Error in get_delivery_time_for_tier: {e}")
        return '2-4 weeks'

def get_project_examples_for_budget(amount: float, tier: str = None):
    """
    Get example projects for a given budget
    
    Args:
        amount: Budget amount
        tier: Budget tier (optional)
    
    Returns:
        List of example projects
    """
    # Example projects database
    examples_database = {
        'basic': [
            "Simple website with contact form",
            "Basic automation script for data processing",
            "Telegram bot with basic commands",
            "Landing page with booking system",
            "Small e-commerce store (up to 50 products)"
        ],
        'standard': [
            "Full e-commerce website with payment integration",
            "Mobile app with user authentication",
            "Custom CRM system for small business",
            "Multi-language website with CMS",
            "Inventory management system"
        ],
        'premium': [
            "Custom marketplace platform",
            "Enterprise CRM with custom workflows",
            "Complex mobile app with real-time features",
            "Custom ERP system for medium business",
            "AI-powered analytics dashboard"
        ],
        'enterprise': [
            "Large-scale SaaS platform",
            "Custom banking/financial system",
            "IoT platform with device management",
            "Healthcare management system",
            "Government portal with multiple integrations"
        ]
    }
    
    # If tier not provided, determine it
    if not tier:
        if amount < 500:
            tier = 'basic'
        elif amount < 1500:
            tier = 'standard'
        elif amount < 3000:
            tier = 'premium'
        else:
            tier = 'enterprise'
    
    # Get examples for tier
    return examples_database.get(tier, [
        "Custom software solution",
        "Tailored application development",
        "Bespoke system integration"
    ])