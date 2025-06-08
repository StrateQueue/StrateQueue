"""Deploy Command Validator

Handles complex validation logic for deploy command arguments including
multi-strategy validation, broker validation, and trading mode validation.
"""

import os
from argparse import Namespace

from ...core.granularity import validate_granularity
from ..utils.deploy_utils import (
    apply_smart_defaults,
    generate_strategy_ids,
    parse_comma_separated,
    parse_symbols,
    validate_allocation_values,
    validate_files_exist,
)
from .base_validator import BaseValidator


class DeployValidator(BaseValidator):
    """Validator for deploy command arguments"""

    def validate(self, args: Namespace) -> tuple[bool, list[str]]:
        """
        Validate deployment arguments with comprehensive checks

        Args:
            args: Parsed command arguments

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Handle legacy --enable-trading flag compatibility
        self._handle_legacy_flags(args)

        # Determine trading configuration early
        self._set_trading_configuration(args)

        # Validate and process strategy configuration
        strategy_errors = self._validate_strategy_configuration(args)
        errors.extend(strategy_errors)

        # Validate symbols format
        symbol_errors = self._validate_symbols(args)
        errors.extend(symbol_errors)

        # Validate duration and other numeric arguments
        numeric_errors = self._validate_numeric_arguments(args)
        errors.extend(numeric_errors)

        # Validate granularity if specified
        granularity_errors = self._validate_granularities(args)
        errors.extend(granularity_errors)

        # Validate broker configuration
        broker_errors = self._validate_brokers(args)
        errors.extend(broker_errors)

        # Validate trading requirements and credentials
        if args._enable_trading:
            trading_errors = self._validate_trading_configuration(args)
            errors.extend(trading_errors)

        return len(errors) == 0, errors

    def _handle_legacy_flags(self, args: Namespace) -> None:
        """Handle deprecated --enable-trading flag"""
        if hasattr(args, 'enable_trading') and args.enable_trading:
            print("⚠️  WARNING: --enable-trading is deprecated. Use --paper or --live instead.")
            if not (args.paper or args.live or args.no_trading):
                # Default to paper trading for legacy compatibility
                args.paper = True

    def _set_trading_configuration(self, args: Namespace) -> None:
        """Set trading configuration flags"""
        # Default to no-trading if no mode specified
        if not (args.paper or args.live or args.no_trading):
            args.no_trading = True

        enable_trading = not args.no_trading
        paper_trading = args.paper

        args._enable_trading = enable_trading
        args._paper_trading = paper_trading

    def _validate_strategy_configuration(self, args: Namespace) -> list[str]:
        """Validate strategy configuration and process multi-strategy arguments"""
        errors = []

        if not args.strategy:
            errors.append("At least one strategy is required")
            return errors

        # Parse comma-separated strategies
        strategies = parse_comma_separated(args.strategy)
        if not strategies:
            errors.append("At least one strategy is required")
            return errors

        # Validate all strategy files exist
        file_errors = validate_files_exist(strategies)
        errors.extend(file_errors)

        # Parse other comma-separated arguments
        strategy_ids = parse_comma_separated(args.strategy_id) if args.strategy_id else []
        allocations = parse_comma_separated(args.allocation) if args.allocation else []
        data_sources = parse_comma_separated(args.data_source) if args.data_source else ['demo']
        granularities = parse_comma_separated(args.granularity) if args.granularity else []
        brokers = parse_comma_separated(args.broker) if args.broker else []

        # Apply smart defaults for multi-value arguments
        try:
            if len(strategies) > 1:
                # Multi-strategy validation
                if not allocations:
                    errors.append("--allocation is required for multi-strategy mode")
                else:
                    allocations = apply_smart_defaults(allocations, len(strategies), "--allocation")

                # Apply smart defaults for other arguments
                data_sources = apply_smart_defaults(data_sources, len(strategies), "--data-source")
                if granularities:
                    granularities = apply_smart_defaults(granularities, len(strategies), "--timeframe")
                if brokers:
                    brokers = apply_smart_defaults(brokers, len(strategies), "--broker")
                if strategy_ids:
                    strategy_ids = apply_smart_defaults(strategy_ids, len(strategies), "--strategy-id")
            else:
                # Single strategy - ensure single values
                data_sources = data_sources[:1] if data_sources else ['demo']
                granularities = granularities[:1] if granularities else []
                brokers = brokers[:1] if brokers else []
                allocations = ['1.0'] if not allocations else allocations[:1]

        except ValueError as e:
            errors.append(str(e))

        # Validate allocation values if we have them
        if allocations:
            allocation_errors = validate_allocation_values(allocations)
            errors.extend(allocation_errors)

        # Generate strategy IDs if not provided
        if not strategy_ids:
            strategy_ids = generate_strategy_ids(strategies)

        # Store parsed values back to args for later use
        args._strategies = strategies
        args._strategy_ids = strategy_ids
        args._allocations = allocations
        args._data_sources = data_sources
        args._granularities = granularities
        args._brokers = brokers

        # Show 1:1 strategy-symbol mapping if applicable
        self._show_strategy_symbol_mapping(strategies, args.symbol)

        return errors

    def _validate_symbols(self, args: Namespace) -> list[str]:
        """Validate symbols format"""
        errors = []

        try:
            symbols = parse_symbols(args.symbol)
            if not symbols or any(not s for s in symbols):
                errors.append("Invalid symbols format. Use comma-separated list like 'AAPL,MSFT'")
        except Exception:
            errors.append("Error parsing symbols")

        return errors

    def _validate_numeric_arguments(self, args: Namespace) -> list[str]:
        """Validate numeric arguments like duration and lookback"""
        errors = []

        # Validate duration
        if args.duration <= 0:
            errors.append("Duration must be a positive number")

        # Validate lookback
        if args.lookback is not None and args.lookback <= 0:
            errors.append("Lookback period must be a positive number")

        return errors

    def _validate_granularities(self, args: Namespace) -> list[str]:
        """Validate granularity for the chosen data source(s)"""
        errors = []

        if hasattr(args, '_granularities') and args._granularities:
            for i, granularity in enumerate(args._granularities):
                if granularity:  # Skip empty granularities
                    data_source = args._data_sources[i] if i < len(args._data_sources) else args._data_sources[0]
                    is_valid, error_msg = validate_granularity(granularity, data_source)
                    if not is_valid:
                        errors.append(f"Invalid granularity '{granularity}' for data source '{data_source}': {error_msg}")

        return errors

    def _validate_brokers(self, args: Namespace) -> list[str]:
        """Validate broker configuration"""
        errors = []

        if hasattr(args, '_brokers') and args._brokers and args._brokers[0]:
            try:
                from ...brokers import get_supported_brokers
                supported = get_supported_brokers()
                for broker in args._brokers:
                    if broker and broker not in supported:
                        errors.append(f"Unsupported broker '{broker}'. Supported: {', '.join(supported)}")
            except ImportError:
                errors.append("Broker functionality not available (missing dependencies)")

        return errors

    def _validate_trading_configuration(self, args: Namespace) -> list[str]:
        """Validate trading requirements and credentials"""
        errors = []

        try:
            from ...brokers import detect_broker_type, validate_broker_credentials

            # If broker specified, validate it
            if hasattr(args, '_brokers') and args._brokers and args._brokers[0]:
                broker = args._brokers[0]
                if not validate_broker_credentials(broker):
                    trading_mode = "paper" if args._paper_trading else "live"
                    errors.append(f"Invalid {trading_mode} trading credentials for broker '{broker}'. Check environment variables.")
            else:
                # Auto-detect broker
                detected_broker = detect_broker_type()
                if detected_broker == 'unknown':
                    trading_mode = "paper" if args._paper_trading else "live"
                    errors.append(f"No broker detected from environment for {trading_mode} trading. Set up broker credentials or use --broker to specify.")
                elif not validate_broker_credentials(detected_broker):
                    trading_mode = "paper" if args._paper_trading else "live"
                    errors.append(f"Invalid {trading_mode} trading credentials for detected broker '{detected_broker}'. Check environment variables.")

            # Special validation for live trading
            if args.live:
                print("🚨 LIVE TRADING MODE ENABLED")
                print("⚠️  You are about to trade with real money!")
                print("💰 Please ensure you have tested your strategy thoroughly in paper trading first.")

        except ImportError:
            errors.append("Trading functionality not available (missing dependencies). Please reinstall the package: pip install stratequeue")

        return errors

    def _show_strategy_symbol_mapping(self, strategies: list[str], symbols_str: str) -> None:
        """Show 1:1 strategy-symbol mapping if applicable"""
        if len(strategies) > 1:
            try:
                symbols = parse_symbols(symbols_str)
                if len(strategies) == len(symbols):
                    print("📌 1:1 Strategy-Symbol mapping detected:")
                    for _i, (strategy, symbol) in enumerate(zip(strategies, symbols, strict=False)):
                        strategy_name = os.path.basename(strategy).replace('.py', '')
                        print(f"   {strategy_name} → {symbol}")
                    print()
            except:
                pass  # symbols might not be parsed yet, ignore validation here
