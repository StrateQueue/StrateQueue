"""
Account Manager for IBKR

Handles account information retrieval and management.
"""

import logging
from typing import Any, Dict, Optional

try:
    from ib_insync import IB
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    
    class IB:
        pass

from ...broker_base import AccountInfo

logger = logging.getLogger(__name__)


class AccountManager:
    """
    Manages account information for IBKR broker.
    
    Handles retrieval and caching of account data including
    cash balances, buying power, and account status.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize the account manager
        
        Args:
            ib_client: Connected ib_insync IB client
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not installed. Install with: pip install stratequeue[ibkr]")
        
        self.ib = ib_client
        self.logger = logging.getLogger(f"{__name__}.AccountManager")
        
        # Cache for account data
        self._account_cache: Optional[Dict[str, Any]] = None
        self._cache_valid = False
    
    def get_account_info(self, force_refresh: bool = False) -> Optional[AccountInfo]:
        """
        Get comprehensive account information
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            AccountInfo object or None if error
        """
        try:
            # Refresh cache if needed
            if force_refresh or not self._cache_valid:
                self._refresh_account_cache()
            
            if not self._account_cache:
                return None
            
            # Extract key values from cache
            account_id = self._get_account_id()
            cash = self._get_cash_balance()
            buying_power = self._get_buying_power()
            total_value = self._get_total_value()
            currency = self._get_base_currency()
            
            return AccountInfo(
                account_id=account_id,
                buying_power=buying_power,
                total_value=total_value,
                cash=cash,
                currency=currency,
                additional_fields=self._get_additional_fields()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    def _refresh_account_cache(self) -> None:
        """Refresh the account data cache"""
        try:
            # Get account summary
            summary = self.ib.accountSummary()
            
            # Convert to dictionary for easier access
            self._account_cache = {}
            for item in summary:
                self._account_cache[item.tag] = {
                    'value': item.value,
                    'currency': item.currency,
                    'account': item.account
                }
            
            self._cache_valid = True
            self.logger.debug(f"Refreshed account cache with {len(summary)} items")
            
        except Exception as e:
            self.logger.error(f"Error refreshing account cache: {e}")
            self._cache_valid = False
    
    def _get_account_id(self) -> str:
        """Get the account ID"""
        if self.ib.wrapper.accounts:
            return self.ib.wrapper.accounts[0]
        return "UNKNOWN"
    
    def _get_cash_balance(self) -> float:
        """Get total cash balance"""
        if not self._account_cache:
            return 0.0
        
        # Try different cash-related fields
        cash_fields = ['TotalCashValue', 'CashBalance', 'AvailableFunds']
        
        for field in cash_fields:
            if field in self._account_cache:
                try:
                    return float(self._account_cache[field]['value'])
                except (ValueError, TypeError):
                    continue
        
        return 0.0
    
    def _get_buying_power(self) -> float:
        """Get buying power"""
        if not self._account_cache:
            return 0.0
        
        # Try buying power related fields
        bp_fields = ['BuyingPower', 'AvailableFunds', 'ExcessLiquidity']
        
        for field in bp_fields:
            if field in self._account_cache:
                try:
                    return float(self._account_cache[field]['value'])
                except (ValueError, TypeError):
                    continue
        
        return 0.0
    
    def _get_total_value(self) -> float:
        """Get total account value"""
        if not self._account_cache:
            return 0.0
        
        # Try net liquidation value first, then other fields
        value_fields = ['NetLiquidation', 'TotalCashValue', 'EquityWithLoanValue']
        
        for field in value_fields:
            if field in self._account_cache:
                try:
                    return float(self._account_cache[field]['value'])
                except (ValueError, TypeError):
                    continue
        
        return 0.0
    
    def _get_base_currency(self) -> str:
        """Get base currency of the account"""
        if not self._account_cache:
            return "USD"
        
        # Look for currency information
        for item in self._account_cache.values():
            if item.get('currency'):
                return item['currency']
        
        return "USD"  # Default to USD
    
    def _get_additional_fields(self) -> Dict[str, Any]:
        """Get additional account fields"""
        additional = {}
        
        if not self._account_cache:
            return additional
        
        # Include useful additional fields
        additional_field_mapping = {
            'DayTradesRemaining': 'day_trades_remaining',
            'Leverage': 'leverage',
            'InitMarginReq': 'initial_margin_requirement',
            'MaintMarginReq': 'maintenance_margin_requirement',
            'RegTEquity': 'reg_t_equity',
            'RegTMargin': 'reg_t_margin',
        }
        
        for ib_field, our_field in additional_field_mapping.items():
            if ib_field in self._account_cache:
                try:
                    additional[our_field] = float(self._account_cache[ib_field]['value'])
                except (ValueError, TypeError):
                    additional[our_field] = self._account_cache[ib_field]['value']
        
        return additional
    
    def get_account_summary_raw(self) -> Dict[str, Any]:
        """
        Get raw account summary data
        
        Returns:
            Dictionary with raw account data
        """
        try:
            if not self._cache_valid:
                self._refresh_account_cache()
            
            return self._account_cache or {}
            
        except Exception as e:
            self.logger.error(f"Error getting raw account summary: {e}")
            return {}
    
    def get_specific_value(self, tag: str) -> Optional[Any]:
        """
        Get a specific account value by tag
        
        Args:
            tag: IB account summary tag
            
        Returns:
            Value for the tag or None if not found
        """
        try:
            if not self._cache_valid:
                self._refresh_account_cache()
            
            if self._account_cache and tag in self._account_cache:
                return self._account_cache[tag]['value']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting specific value for {tag}: {e}")
            return None
    
    def is_pattern_day_trader(self) -> bool:
        """
        Check if account is flagged as pattern day trader
        
        Returns:
            True if account is PDT
        """
        try:
            day_trades_remaining = self.get_specific_value('DayTradesRemaining')
            if day_trades_remaining is not None:
                # If day trades remaining is 0, likely a PDT account
                return float(day_trades_remaining) == 0
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking PDT status: {e}")
            return False
    
    def get_margin_info(self) -> Dict[str, float]:
        """
        Get margin-related information
        
        Returns:
            Dictionary with margin information
        """
        margin_info = {}
        
        try:
            margin_fields = {
                'InitMarginReq': 'initial_margin_requirement',
                'MaintMarginReq': 'maintenance_margin_requirement',
                'AvailableFunds': 'available_funds',
                'ExcessLiquidity': 'excess_liquidity',
                'Leverage': 'leverage'
            }
            
            for ib_field, our_field in margin_fields.items():
                value = self.get_specific_value(ib_field)
                if value is not None:
                    try:
                        margin_info[our_field] = float(value)
                    except (ValueError, TypeError):
                        margin_info[our_field] = 0.0
            
            return margin_info
            
        except Exception as e:
            self.logger.error(f"Error getting margin info: {e}")
            return {}
    
    def invalidate_cache(self) -> None:
        """Invalidate the account cache to force refresh on next access"""
        self._cache_valid = False
 