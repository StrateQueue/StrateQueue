"""
Signal Coordination

Handles signal generation and validation across multiple strategies:
- Strategy initialization and lifecycle management
- Multi-strategy signal generation
- Signal validation against portfolio constraints
- Strategy status tracking
- Hot swapping strategies at runtime
"""

import logging

from ..core.signal_extractor import LiveSignalExtractor, SignalType, TradingSignal
from ..core.strategy_loader import StrategyLoader
from .strategy_config import StrategyConfig

logger = logging.getLogger(__name__)


class SignalCoordinator:
    """Coordinates signal generation across multiple strategies"""

    def __init__(self, strategy_configs: dict[str, StrategyConfig]):
        """
        Initialize SignalCoordinator

        Args:
            strategy_configs: Dictionary of strategy configurations
        """
        self.strategy_configs = strategy_configs
        self.strategy_status: dict[str, str] = {}
        self.active_signals: dict[str, dict[str, TradingSignal]] = (
            {}
        )  # strategy_id -> symbol -> signal
        self.paused_strategies: set = set()  # Track paused strategies

    def initialize_strategies(self):
        """Load and initialize all strategy classes"""
        logger.info("Initializing strategy classes...")

        for strategy_id, config in self.strategy_configs.items():
            self._initialize_single_strategy(strategy_id, config)

        logger.info(f"Successfully initialized {len(self.strategy_configs)} strategies")

    def _initialize_single_strategy(self, strategy_id: str, config: StrategyConfig):
        """Initialize a single strategy (helper method for hot swapping)"""
        try:
            # Use cached strategy class or load from file if not cached
            if config.strategy_class is not None:
                strategy_class = config.strategy_class
            else:
                # Load strategy class from file (fallback if not cached)
                strategy_class = StrategyLoader.load_strategy_from_file(config.file_path)
                config.strategy_class = strategy_class

            # Convert to signal-generating strategy
            signal_strategy_class = StrategyLoader.convert_to_signal_strategy(strategy_class)

            # Create signal extractor with individual strategy's lookback requirement
            signal_extractor = LiveSignalExtractor(
                signal_strategy_class, min_bars_required=config.lookback_period
            )

            # Update config
            config.strategy_class = signal_strategy_class
            config.signal_extractor = signal_extractor

            # Initialize strategy status
            self.strategy_status[strategy_id] = "initialized"

            logger.info(
                f"✅ Initialized strategy: {strategy_id} (lookback: {config.lookback_period})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize strategy {strategy_id}: {e}")
            self.strategy_status[strategy_id] = f"error: {e}"
            raise

    # HOT SWAP METHODS

    def add_strategy_runtime(self, strategy_id: str, config: StrategyConfig) -> bool:
        """
        Add a new strategy at runtime

        Args:
            strategy_id: Unique identifier for the strategy
            config: Strategy configuration

        Returns:
            True if strategy was added successfully
        """
        try:
            if strategy_id in self.strategy_configs:
                logger.warning(f"Strategy {strategy_id} already exists, skipping add")
                return False

            # Add to configurations
            self.strategy_configs[strategy_id] = config

            # Initialize the strategy
            self._initialize_single_strategy(strategy_id, config)

            logger.info(f"🔥 Hot-added strategy: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to hot-add strategy {strategy_id}: {e}")
            # Clean up on failure
            if strategy_id in self.strategy_configs:
                del self.strategy_configs[strategy_id]
            if strategy_id in self.strategy_status:
                del self.strategy_status[strategy_id]
            return False

    def remove_strategy_runtime(self, strategy_id: str) -> bool:
        """
        Remove a strategy at runtime

        Args:
            strategy_id: Strategy to remove

        Returns:
            True if strategy was removed successfully
        """
        try:
            if strategy_id not in self.strategy_configs:
                logger.warning(f"Strategy {strategy_id} not found, cannot remove")
                return False

            # Remove from all tracking structures
            del self.strategy_configs[strategy_id]
            if strategy_id in self.strategy_status:
                del self.strategy_status[strategy_id]
            if strategy_id in self.active_signals:
                del self.active_signals[strategy_id]
            self.paused_strategies.discard(strategy_id)

            logger.info(f"🔥 Hot-removed strategy: {strategy_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to hot-remove strategy {strategy_id}: {e}")
            return False

    def pause_strategy(self, strategy_id: str) -> bool:
        """
        Pause a strategy (stops signal generation but keeps config)

        Args:
            strategy_id: Strategy to pause

        Returns:
            True if strategy was paused successfully
        """
        if strategy_id not in self.strategy_configs:
            logger.warning(f"Strategy {strategy_id} not found, cannot pause")
            return False

        self.paused_strategies.add(strategy_id)
        self.strategy_status[strategy_id] = "paused"

        # Clear active signals for paused strategy
        if strategy_id in self.active_signals:
            del self.active_signals[strategy_id]

        logger.info(f"⏸️ Paused strategy: {strategy_id}")
        return True

    def resume_strategy(self, strategy_id: str) -> bool:
        """
        Resume a paused strategy

        Args:
            strategy_id: Strategy to resume

        Returns:
            True if strategy was resumed successfully
        """
        if strategy_id not in self.strategy_configs:
            logger.warning(f"Strategy {strategy_id} not found, cannot resume")
            return False

        self.paused_strategies.discard(strategy_id)
        self.strategy_status[strategy_id] = "initialized"

        logger.info(f"▶️ Resumed strategy: {strategy_id}")
        return True

    def is_strategy_paused(self, strategy_id: str) -> bool:
        """Check if a strategy is paused"""
        return strategy_id in self.paused_strategies

    async def generate_signals(self, symbol: str, historical_data) -> dict[str, TradingSignal]:
        """
        Generate signals from strategies for a given symbol

        In 1:1 mapping mode, only generates signals from strategies configured for this symbol.
        In traditional mode, generates signals from all strategies.

        Args:
            symbol: Symbol to generate signals for
            historical_data: Historical price data

        Returns:
            Dictionary mapping strategy_id to TradingSignal
        """
        signals = {}

        for strategy_id, config in self.strategy_configs.items():
            if not config.signal_extractor:
                continue

            # Skip paused strategies
            if self.is_strategy_paused(strategy_id):
                continue

            # Check if this strategy should run on this symbol
            # If config.symbol is None, it runs on all symbols (traditional mode)
            # If config.symbol is set, it only runs on that specific symbol (1:1 mode)
            if config.symbol is not None and config.symbol != symbol:
                continue

            try:
                # Extract signal from strategy
                signal = config.signal_extractor.extract_signal(historical_data)

                # Add strategy ID to signal
                signal.strategy_id = strategy_id

                signals[strategy_id] = signal

                # Update active signals tracking
                if strategy_id not in self.active_signals:
                    self.active_signals[strategy_id] = {}
                self.active_signals[strategy_id][symbol] = signal

                # Log non-hold signals
                if signal.signal != SignalType.HOLD:
                    logger.info(
                        f"Signal from {strategy_id} for {symbol}: {signal.signal.value} "
                        f"@ ${signal.price:.2f}"
                    )

            except Exception as e:
                logger.error(f"Error generating signal from {strategy_id} for {symbol}: {e}")
                # Create error signal
                signals[strategy_id] = TradingSignal(
                    signal=SignalType.HOLD,
                    price=0.0,
                    timestamp=historical_data.index[-1] if len(historical_data) > 0 else None,
                    indicators={},
                    strategy_id=strategy_id,
                )

        return signals

    def validate_signal(
        self, signal: TradingSignal, symbol: str, portfolio_manager
    ) -> tuple[bool, str]:
        """
        Validate a signal against portfolio constraints

        Args:
            signal: Trading signal to validate
            symbol: Symbol the signal is for
            portfolio_manager: Portfolio manager instance for validation

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if not portfolio_manager:
            return False, "Portfolio manager not initialized"

        strategy_id = signal.strategy_id
        if not strategy_id:
            return False, "Signal missing strategy_id"

        # Validate buy signals
        if signal.signal in [
            SignalType.BUY,
            SignalType.LIMIT_BUY,
            SignalType.STOP_BUY,
            SignalType.STOP_LIMIT_BUY,
        ]:

            # Estimate order amount (simplified calculation)
            # In practice, this would need account value and signal size
            estimated_amount = 1000.0  # Placeholder - should be calculated properly
            if hasattr(signal, "size") and signal.size:
                estimated_amount *= signal.size

            return portfolio_manager.can_buy(strategy_id, symbol, estimated_amount)

        # Validate sell signals
        elif signal.signal in [
            SignalType.SELL,
            SignalType.CLOSE,
            SignalType.LIMIT_SELL,
            SignalType.STOP_SELL,
            SignalType.STOP_LIMIT_SELL,
            SignalType.TRAILING_STOP_SELL,
        ]:

            # Use None for quantity to check full position sell capability
            return portfolio_manager.can_sell(strategy_id, symbol, None)

        # Hold signals are always valid
        elif signal.signal == SignalType.HOLD:
            return True, "OK"

        return False, f"Unknown signal type: {signal.signal}"

    def get_strategy_status(self, strategy_id: str) -> str:
        """Get status of a specific strategy"""
        return self.strategy_status.get(strategy_id, "unknown")

    def get_all_strategy_statuses(self) -> dict[str, str]:
        """Get status of all strategies"""
        return self.strategy_status.copy()

    def get_active_signals(self) -> dict[str, dict[str, TradingSignal]]:
        """Get all currently active signals"""
        return self.active_signals.copy()

    def get_signals_for_symbol(self, symbol: str) -> dict[str, TradingSignal]:
        """Get all active signals for a specific symbol"""
        signals = {}
        for strategy_id, symbol_signals in self.active_signals.items():
            if symbol in symbol_signals:
                signals[strategy_id] = symbol_signals[symbol]
        return signals

    def clear_signals_for_symbol(self, symbol: str):
        """Clear all signals for a specific symbol"""
        for strategy_id in self.active_signals:
            if symbol in self.active_signals[strategy_id]:
                del self.active_signals[strategy_id][symbol]

    def get_strategy_count(self) -> int:
        """Get total number of strategies"""
        return len(self.strategy_configs)

    def is_strategy_active(self, strategy_id: str) -> bool:
        """Check if a strategy is active and working"""
        status = self.strategy_status.get(strategy_id, "unknown")
        return status == "initialized" or status == "running"
