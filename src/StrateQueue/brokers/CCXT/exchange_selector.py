"""
Interactive Exchange Selection System

Provides CLI interface for selecting cryptocurrency exchanges during setup.
"""

import logging
from typing import Optional, Tuple

try:
    from questionary import select, text
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False

from .exchange_config import ExchangeConfig, ExchangeInfo

logger = logging.getLogger(__name__)


class ExchangeSelector:
    """Interactive exchange selection for CLI setup"""
    
    def __init__(self):
        self.config = ExchangeConfig()
    
    def show_exchange_menu(self) -> str:
        """
        Display interactive menu for exchange selection
        
        Returns:
            Selected exchange ID
        """
        if not QUESTIONARY_AVAILABLE:
            # Fallback to old method if questionary is not available
            return self._show_exchange_menu_fallback()
        
        print("\n🏦 CCXT Exchange Selection")
        print("=" * 60)
        
        # Get top 10 exchanges
        top_exchanges = self.config.get_top_10_exchanges()
        
        # Create choices for questionary
        choices = []
        exchange_map = {}
        
        # Add popular exchanges
        for exchange in top_exchanges:
            sandbox_indicator = "🧪" if exchange.supports_sandbox else "🔴"
            passphrase_indicator = "🔑" if exchange.requires_passphrase else ""
            display_name = f"{exchange.name} ({exchange.id}) {sandbox_indicator} {passphrase_indicator}"
            choices.append(display_name)
            exchange_map[display_name] = exchange
        
        # Add manual input option
        manual_option = "📝 Manual input (other exchange)"
        choices.append(manual_option)
        
        print("\n🧪 = Testnet/Sandbox available")
        print("🔑 = Requires passphrase") 
        print("🔴 = Live trading only")
        
        try:
            # Show selection menu
            choice = select(
                "Select a cryptocurrency exchange:",
                choices=choices
            ).ask()
            
            if choice is None:
                raise KeyboardInterrupt("User cancelled exchange selection")
            
            # Handle manual input
            if choice == manual_option:
                return self._handle_manual_input()
            
            # Handle exchange selection
            selected_exchange = exchange_map[choice]
            print(f"\n✅ Selected: {selected_exchange.name} ({selected_exchange.id})")
            self._show_exchange_details(selected_exchange)
            return selected_exchange.id
            
        except KeyboardInterrupt:
            print("\n❌ Setup cancelled by user.")
            raise
    
    def _handle_manual_input(self) -> str:
        """Handle manual exchange input with validation and suggestions"""
        if not QUESTIONARY_AVAILABLE:
            return self._handle_manual_input_fallback()
        
        print("\n" + "-"*50)
        print("📝 Manual Exchange Input")
        print("-"*50)
        print("💡 You can enter an exchange ID or select from options below")
        
        while True:
            try:
                # Create dynamic choices
                choices = [
                    "🔍 Enter exchange ID manually",
                    "📋 Show all supported exchanges",
                    "🔙 Back to main menu"
                ]
                
                action = select(
                    "What would you like to do?",
                    choices=choices
                ).ask()
                
                if action is None or "Back to main menu" in action:
                    return self.show_exchange_menu()
                
                if "Show all supported exchanges" in action:
                    self._show_all_exchanges()
                    continue
                
                if "Enter exchange ID manually" in action:
                    exchange_input = text(
                        "Exchange ID (e.g., 'bittrex', 'poloniex', 'gemini'):"
                    ).ask()
                    
                    if not exchange_input:
                        continue
                    
                    exchange_input = exchange_input.strip().lower()
                    
                    # Validate exchange
                    if self.validate_exchange(exchange_input):
                        exchange_info = self.config.get_exchange_info(exchange_input)
                        print(f"\n✅ Valid exchange: {exchange_input}")
                        if exchange_info:
                            self._show_exchange_details(exchange_info)
                        return exchange_input
                    else:
                        # Show suggestions
                        suggestions = self.config.suggest_similar_exchanges(exchange_input)
                        if suggestions:
                            print(f"\n❌ '{exchange_input}' not found. Did you mean:")
                            suggestion_choices = [f"{suggestion}" for suggestion in suggestions]
                            suggestion_choices.append("🔄 Try again")
                            suggestion_choices.append("🔙 Back to menu")
                            
                            suggestion_choice = select(
                                "Select a suggested exchange:",
                                choices=suggestion_choices
                            ).ask()
                            
                            if suggestion_choice is None or "Back to menu" in suggestion_choice:
                                continue
                            elif "Try again" in suggestion_choice:
                                continue
                            else:
                                # User selected a suggestion
                                selected_exchange = suggestion_choice
                                exchange_info = self.config.get_exchange_info(selected_exchange)
                                print(f"\n✅ Selected: {selected_exchange}")
                                if exchange_info:
                                    self._show_exchange_details(exchange_info)
                                return selected_exchange
                        else:
                            print(f"\n❌ '{exchange_input}' is not a supported exchange.")
                            continue_choice = select(
                                "What would you like to do?",
                                choices=["🔄 Try again", "📋 Show all exchanges", "🔙 Back to menu"]
                            ).ask()
                            
                            if continue_choice is None or "Back to menu" in continue_choice:
                                continue
                            elif "Show all exchanges" in continue_choice:
                                self._show_all_exchanges()
                                continue
                            else:
                                continue
                
            except KeyboardInterrupt:
                print("\n\n❌ Returning to main menu...")
                return self.show_exchange_menu()
            except Exception as e:
                logger.error(f"Error in manual input: {e}")
                print(f"❌ Error: {e}")
                continue
    
    def _show_exchange_details(self, exchange_info: ExchangeInfo):
        """Display detailed information about selected exchange"""
        print(f"\n📋 Exchange Details:")
        print(f"   Name: {exchange_info.name}")
        print(f"   ID: {exchange_info.id}")
        print(f"   Testnet/Sandbox: {'✅ Available' if exchange_info.supports_sandbox else '❌ Not available'}")
        print(f"   Passphrase Required: {'✅ Yes' if exchange_info.requires_passphrase else '❌ No'}")
        print(f"   API Permissions: {', '.join(exchange_info.api_permissions)}")
        print(f"\n💡 Setup Instructions:")
        print(f"   {exchange_info.setup_instructions}")
    
    def _show_all_exchanges(self):
        """Display all supported exchanges in a paginated format"""
        all_exchanges = self.config.get_all_supported_exchanges()
        
        if not all_exchanges:
            print("❌ Could not retrieve exchange list. CCXT may not be installed.")
            return
        
        print(f"\n📋 All Supported Exchanges ({len(all_exchanges)} total):")
        print("-" * 60)
        
        # Display in columns
        exchanges_per_row = 4
        for i in range(0, len(all_exchanges), exchanges_per_row):
            row_exchanges = all_exchanges[i:i + exchanges_per_row]
            formatted_row = "  ".join(f"{ex:<15}" for ex in row_exchanges)
            print(formatted_row)
        
        print("-" * 60)
    
    def validate_exchange(self, exchange_id: str) -> bool:
        """Validate if exchange is supported"""
        return self.config.validate_exchange(exchange_id)
    
    def get_exchange_requirements(self, exchange_id: str) -> Optional[ExchangeInfo]:
        """Get requirements for specific exchange"""
        return self.config.get_exchange_info(exchange_id)
    
    def prompt_for_confirmation(self, exchange_id: str) -> bool:
        """Prompt user to confirm exchange selection"""
        if not QUESTIONARY_AVAILABLE:
            return self._prompt_for_confirmation_fallback(exchange_id)
        
        try:
            choice = select(
                f"Confirm selection of {exchange_id}?",
                choices=["✅ Yes, proceed with this exchange", "❌ No, go back to selection"]
            ).ask()
            
            if choice is None:
                return False
            
            return "Yes, proceed" in choice
            
        except KeyboardInterrupt:
            return False
    
    def _show_exchange_menu_fallback(self) -> str:
        """
        Fallback exchange selection when questionary is not available
        
        Returns:
            Selected exchange ID
        """
        print("\n🏦 CCXT Exchange Selection")
        print("=" * 60)
        print("💡 Interactive mode not available. Install questionary for better experience: pip install questionary")
        
        # Get top 10 exchanges
        top_exchanges = self.config.get_top_10_exchanges()
        
        print("\n📋 Popular Exchanges:")
        for i, exchange in enumerate(top_exchanges, 1):
            sandbox_indicator = "🧪" if exchange.supports_sandbox else "🔴"
            passphrase_indicator = "🔑" if exchange.requires_passphrase else ""
            print(f"  {i:2d}. {exchange.name} ({exchange.id}) {sandbox_indicator} {passphrase_indicator}")
        
        print(f"\n  {len(top_exchanges) + 1:2d}. Manual input (other exchange)")
        
        print("\n🧪 = Testnet/Sandbox available")
        print("🔑 = Requires passphrase") 
        print("🔴 = Live trading only")
        
        while True:
            try:
                choice_input = input(f"\nSelect exchange (1-{len(top_exchanges) + 1}): ").strip()
                
                if not choice_input:
                    continue
                
                try:
                    choice_num = int(choice_input)
                    if 1 <= choice_num <= len(top_exchanges):
                        selected_exchange = top_exchanges[choice_num - 1]
                        print(f"\n✅ Selected: {selected_exchange.name} ({selected_exchange.id})")
                        self._show_exchange_details(selected_exchange)
                        return selected_exchange.id
                    elif choice_num == len(top_exchanges) + 1:
                        return self._handle_manual_input_fallback()
                    else:
                        print(f"❌ Please enter a number between 1 and {len(top_exchanges) + 1}")
                except ValueError:
                    print("❌ Please enter a valid number")
                    
            except KeyboardInterrupt:
                print("\n❌ Setup cancelled by user.")
                raise
    
    def _handle_manual_input_fallback(self) -> str:
        """Fallback manual input when questionary is not available"""
        print("\n" + "-"*50)
        print("📝 Manual Exchange Input")
        print("-"*50)
        print("Enter the exchange ID (e.g., 'bittrex', 'poloniex', 'gemini')")
        print("Type 'list' to see all supported exchanges")
        print("Type 'back' to return to the main menu")
        
        while True:
            try:
                exchange_input = input("\nExchange ID: ").strip().lower()
                
                if not exchange_input:
                    continue
                
                if exchange_input == 'back':
                    return self._show_exchange_menu_fallback()
                
                if exchange_input == 'list':
                    self._show_all_exchanges()
                    continue
                
                # Validate exchange
                if self.validate_exchange(exchange_input):
                    exchange_info = self.config.get_exchange_info(exchange_input)
                    print(f"\n✅ Valid exchange: {exchange_input}")
                    if exchange_info:
                        self._show_exchange_details(exchange_info)
                    return exchange_input
                else:
                    # Show suggestions
                    suggestions = self.config.suggest_similar_exchanges(exchange_input)
                    if suggestions:
                        print(f"\n❌ '{exchange_input}' not found. Did you mean:")
                        for i, suggestion in enumerate(suggestions, 1):
                            print(f"  {i}. {suggestion}")
                        print("\nTry again or type 'list' to see all exchanges.")
                    else:
                        print(f"\n❌ '{exchange_input}' is not a supported exchange.")
                        print("Type 'list' to see all supported exchanges.")
                
            except KeyboardInterrupt:
                print("\n\n❌ Returning to main menu...")
                return self._show_exchange_menu_fallback()
            except Exception as e:
                logger.error(f"Error in manual input: {e}")
                print(f"❌ Error: {e}")
    
    def _prompt_for_confirmation_fallback(self, exchange_id: str) -> bool:
        """Fallback confirmation prompt when questionary is not available"""
        while True:
            try:
                confirm = input(f"\nConfirm selection of {exchange_id}? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return True
                elif confirm in ['n', 'no']:
                    return False
                else:
                    print("Please enter 'y' for yes or 'n' for no.")
            except KeyboardInterrupt:
                return False