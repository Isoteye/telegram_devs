"""
Currency conversion service for multi-currency support
"""
import requests
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

class CurrencyService:
    def __init__(self):
        # Currency exchange rates (fallback rates)
        # Updated with realistic rates
        self.fallback_rates = {
            'USD': 1.0,
            'GHS': 12.0,  # 1 USD = 12 GHS (Ghanaian Cedi)
            'NGN': 1500.0,  # 1 USD = 1500 NGN (Nigerian Naira)
            'KES': 150.0,  # 1 USD = 150 KES (Kenyan Shilling)
            'ZAR': 18.0,  # 1 USD = 18 ZAR (South African Rand)
            'EUR': 0.92,  # 1 USD = 0.92 EUR
            'GBP': 0.79,  # 1 USD = 0.79 GBP
            'INR': 83.0,  # 1 USD = 83 INR (Indian Rupee)
            'CAD': 1.35,  # 1 USD = 1.35 CAD
            'AUD': 1.51,  # 1 USD = 1.51 AUD
        }
        
        self.currency_symbols = {
            'USD': '$',
            'GHS': 'GH₵',
            'NGN': '₦',
            'KES': 'KSh',
            'ZAR': 'R',
            'EUR': '€',
            'GBP': '£',
            'INR': '₹',
            'CAD': 'CA$',
            'AUD': 'A$',
        }
        
        # Cache for exchange rates
        self.rates_cache = {}
        self.cache_expiry = datetime.now()
        self.cache_duration = timedelta(hours=1)  # Cache rates for 1 hour
    
    def get_exchange_rates(self, force_refresh: bool = False) -> Dict[str, float]:
        """Get exchange rates from API with fallback"""
        
        # Check cache first
        if not force_refresh and self.rates_cache and datetime.now() < self.cache_expiry:
            logger.info("Using cached exchange rates")
            return self.rates_cache
        
        try:
            # Try to get rates from Open Exchange Rates (free tier)
            api_key = os.getenv('OPEN_EXCHANGE_RATES_API_KEY', '')
            if api_key:
                response = requests.get(
                    f"https://openexchangerates.org/api/latest.json?app_id={api_key}&base=USD",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    rates = data.get('rates', {})
                    
                    # Add USD rate
                    rates['USD'] = 1.0
                    
                    # Update cache
                    self.rates_cache = rates
                    self.cache_expiry = datetime.now() + self.cache_duration
                    
                    logger.info(f"Successfully fetched exchange rates for {len(rates)} currencies")
                    return rates
                else:
                    logger.warning(f"Failed to fetch exchange rates: {response.status_code}")
            
            # Try Fixer.io as backup
            api_key = os.getenv('FIXER_API_KEY', '')
            if api_key:
                response = requests.get(
                    f"http://data.fixer.io/api/latest?access_key={api_key}&base=EUR&symbols=USD,GHS,NGN,KES,ZAR,GBP,INR,CAD,AUD",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        # Convert from EUR base to USD base
                        eur_rates = data.get('rates', {})
                        usd_to_eur = 1 / eur_rates.get('USD', 0.92)
                        
                        rates = {'USD': 1.0}
                        for currency, rate in eur_rates.items():
                            if currency != 'USD':
                                rates[currency] = rate * usd_to_eur
                        
                        # Update cache
                        self.rates_cache = rates
                        self.cache_expiry = datetime.now() + self.cache_duration
                        
                        logger.info(f"Successfully fetched exchange rates from Fixer for {len(rates)} currencies")
                        return rates
                    
        except Exception as e:
            logger.error(f"Error fetching exchange rates: {e}")
        
        # Fallback to hardcoded rates
        logger.info("Using fallback exchange rates")
        return self.fallback_rates
    
    def convert_usd_to_currency(self, usd_amount: float, target_currency: str) -> float:
        """Convert USD to target currency"""
        try:
            from config import EXCHANGE_RATES
            rate = EXCHANGE_RATES.get(target_currency.upper(), 1.0)
            return usd_amount * rate
        except:
            return usd_amount
    
    def convert_currency_to_usd(self, amount: float, source_currency: str) -> float:
        """Convert from any currency to USD"""
        try:
            from config import EXCHANGE_RATES
            rate = EXCHANGE_RATES.get(source_currency.upper(), 1.0)
            return amount / rate if rate != 0 else amount
        except:
            return amount
    
    def get_currency_symbol(self, currency_code: str) -> str:
        """Get symbol for currency code"""
        currency_code = currency_code.upper()
        return self.currency_symbols.get(currency_code, '$')
    
    def get_country_currency(self, country_code: str) -> str:
        """Get currency for country code"""
        country_currencies = {
            'US': 'USD',
            'GH': 'GHS',
            'NG': 'NGN',
            'KE': 'KES',
            'ZA': 'ZAR',
            'GB': 'GBP',
            'IN': 'INR',
            'CA': 'CAD',
            'AU': 'AUD',
            'DE': 'EUR', 'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR', 'NL': 'EUR',
        }
        return country_currencies.get(country_code.upper(), 'USD')
    
    def format_currency(self, amount: float, currency_code: str) -> str:
        """Format amount with currency symbol"""
        symbol = self.get_currency_symbol(currency_code)
        
        if currency_code == 'GHS':
            return f"GH₵{amount:,.2f}"
        elif currency_code == 'NGN':
            return f"₦{amount:,.2f}"
        elif currency_code == 'KES':
            return f"KSh{amount:,.2f}"
        elif currency_code == 'ZAR':
            return f"R{amount:,.2f}"
        elif currency_code == 'INR':
            return f"₹{amount:,.2f}"
        elif currency_code == 'EUR':
            return f"€{amount:,.2f}"
        elif currency_code == 'GBP':
            return f"£{amount:,.2f}"
        elif currency_code == 'CAD':
            return f"CA${amount:,.2f}"
        elif currency_code == 'AUD':
            return f"A${amount:,.2f}"
        else:
            return f"${amount:,.2f}"


# Global instance
currency_service = CurrencyService()