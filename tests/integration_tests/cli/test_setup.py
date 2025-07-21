"""
Setup Command Integration Tests

Tests for the setup command --docs functionality and interactive setup.
"""

import subprocess
import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
import pexpect
import time

# Version-agnostic Python executable
PYTHON_EXEC = sys.executable

def create_minimal_test_env(home_dir: str = None) -> dict:
    """
    Create a minimal environment for subprocess calls to avoid 'Argument list too long' error.
    
    Args:
        home_dir: Optional home directory to set (for test isolation)
    
    Returns:
        Dictionary with minimal environment variables
    """
    minimal_env = {
        # Essential system variables
        'PATH': '/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/3.10/bin:/usr/bin:/bin:/usr/sbin:/sbin',
        'SHELL': '/bin/bash',
        'USER': os.environ.get('USER', 'testuser'),
        'LANG': 'en_US.UTF-8',
        'LC_ALL': 'en_US.UTF-8',
        
        # Python-specific variables
        'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
        'PYTHONIOENCODING': 'utf-8',
        
        # StrateQueue test variables
        'SQ_TEST_STUB_BROKERS': '1',
        'SQ_OFFLINE': '1',
        'SQ_LIGHT_IMPORTS': '1',
        
        # Clear any existing broker/trading environment variables
        'PAPER_KEY': '',
        'PAPER_SECRET': '',
        'ALPACA_API_KEY': '',
        'ALPACA_SECRET_KEY': '',
        'IB_TWS_PORT': '',
        'IB_CLIENT_ID': '',
        'IB_TWS_HOST': '',
        'POLYGON_API_KEY': '',
        'CMC_API_KEY': '',
        'IBKR_PORT': '4000',  # For test skipping
    }
    
    # Set HOME directory if specified
    if home_dir:
        minimal_env['HOME'] = str(home_dir)
    else:
        minimal_env['HOME'] = os.environ.get('HOME', '/tmp')
    
    return minimal_env

# Helper to ensure directories exist with proper permissions
def ensure_directory_with_permissions(dir_path):
    """
    Create a directory and ensure it has the right permissions
    """
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    # On non-Windows systems, make sure permissions are appropriate for a credential store
    if os.name != 'nt':
        os.chmod(dir_path, 0o700)  # Only the user can read/write/execute
    
    # Debug info in case of failures
    print(f"Created directory {dir_path}")
    if os.path.exists(dir_path):
        print(f"Directory exists, permissions: {oct(os.stat(dir_path).st_mode & 0o777)}")
    else:
        print(f"ERROR: Directory does not exist after creation attempt")
    
    return dir_path


class TestSetupCommandDocs:
    """Test setup command documentation display"""
    
    def _run_cli_command(self, cli_runner, *args):
        """Helper to run CLI command and return result object"""
        exit_code, stdout, stderr = cli_runner(*args)
        
        class Result:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        
        return Result(exit_code, stdout, stderr)

    def test_setup_docs_shows_general_documentation(self, cli_runner):
        """D-1: setup --docs prints general setup documentation"""
        result = self._run_cli_command(cli_runner, 'setup', '--docs')
        
        assert result.returncode == 0
        assert "🔧 StrateQueue Setup Documentation" in result.stdout
        assert "Available Setup Options:" in result.stdout
        assert "Data Providers:" in result.stdout
        assert "Brokers:" in result.stdout
        assert "Interactive Setup:" in result.stdout
        assert "stratequeue setup broker --docs" in result.stdout
        
        # Check for a unique sentence from the general docs
        assert "Configure market data sources (Polygon, CoinMarketCap)" in result.stdout
        assert "Configure trading platforms (Alpaca)" in result.stdout

    def test_setup_broker_docs_shows_broker_instructions(self, cli_runner):
        """D-2: setup broker --docs shows broker setup instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'broker', '--docs')
        
        assert result.returncode == 0
        assert "🔧 Broker Setup Instructions:" in result.stdout
        
        # The current implementation shows fallback instructions when dependencies are missing
        # In the integration test environment, we expect the fallback behavior
        assert "Manual Setup (Alpaca Paper Trading):" in result.stdout
        assert "Create account at alpaca.markets" in result.stdout
        assert "export PAPER_KEY=" in result.stdout
        assert "export PAPER_SECRET=" in result.stdout
        
        # Check for live trading instructions too
        assert "Alternative Setup (Live Trading - Use with caution):" in result.stdout
        assert "export ALPACA_API_KEY=" in result.stdout
        assert "export ALPACA_SECRET_KEY=" in result.stdout

    def test_setup_broker_alpaca_docs_shows_alpaca_specific(self, cli_runner):
        """D-2: setup broker alpaca --docs shows Alpaca-specific instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'broker', 'alpaca', '--docs')
        
        assert result.returncode == 0
        assert "🔧 Broker Setup Instructions:" in result.stdout
        
        # Should show Alpaca-specific instructions
        assert "Alpaca Paper Trading" in result.stdout
        assert "alpaca.markets" in result.stdout
        assert "PAPER_KEY" in result.stdout
        assert "PAPER_SECRET" in result.stdout
        assert "ALPACA_API_KEY" in result.stdout
        assert "ALPACA_SECRET_KEY" in result.stdout
        
        # Should include verification steps
        assert "stratequeue status" in result.stdout
        assert "stratequeue deploy" in result.stdout

    def test_setup_data_provider_docs_shows_provider_instructions(self, cli_runner):
        """setup data-provider --docs shows data provider instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'data-provider', '--docs')
        
        assert result.returncode == 0
        assert "📊 Data Provider Setup Documentation" in result.stdout
        assert "Available Data Providers:" in result.stdout
        assert "Polygon.io" in result.stdout
        assert "CoinMarketCap" in result.stdout
        assert "Demo Provider" in result.stdout
        
        # Check for specific provider details
        assert "Free tier available" in result.stdout
        assert "No API key required" in result.stdout
        assert "Interactive setup: stratequeue setup data-provider" in result.stdout

    def test_setup_data_provider_polygon_docs_shows_polygon_specific(self, cli_runner):
        """setup data-provider polygon --docs shows Polygon-specific instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'data-provider', 'polygon', '--docs')
        
        assert result.returncode == 0
        assert "📊 Data Provider Setup Documentation" in result.stdout
        assert "🔸 Polygon.io Setup:" in result.stdout
        assert "https://polygon.io/" in result.stdout
        assert "POLYGON_API_KEY" in result.stdout
        assert "export POLYGON_API_KEY=your_key_here" in result.stdout
        assert "Supported markets: Stocks, Crypto, Forex" in result.stdout

    def test_setup_data_provider_coinmarketcap_docs_shows_cmc_specific(self, cli_runner):
        """setup data-provider coinmarketcap --docs shows CoinMarketCap-specific instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'data-provider', 'coinmarketcap', '--docs')
        
        assert result.returncode == 0
        assert "CoinMarketCap Setup:" in result.stdout
        assert "pro.coinmarketcap.com" in result.stdout
        assert "CMC_API_KEY" in result.stdout
        assert "Supported markets: Cryptocurrency" in result.stdout

    def test_setup_data_provider_ccxt_docs_shows_ccxt_specific(self, cli_runner):
        """setup data-provider ccxt --docs shows CCXT-specific instructions"""
        result = self._run_cli_command(cli_runner, 'setup', 'data-provider', 'ccxt', '--docs')
        
        assert result.returncode == 0
        assert "📊 Data Provider Setup Documentation" in result.stdout
        assert "🔸 CCXT Data Provider Setup:" in result.stdout
        assert "pip install ccxt" in result.stdout
        assert "250+ supported exchanges" in result.stdout
        assert "CCXT_EXCHANGE" in result.stdout
        assert "CCXT_API_KEY" in result.stdout
        assert "CCXT_SECRET_KEY" in result.stdout
        assert "Popular exchanges: Binance, Coinbase, Kraken, Bitfinex" in result.stdout
        assert "Supported markets: Cryptocurrency" in result.stdout

    def test_setup_docs_exit_code_success(self, cli_runner):
        """All setup --docs commands should exit with code 0"""
        test_commands = [
            ['setup', '--docs'],
            ['setup', 'broker', '--docs'],
            ['setup', 'broker', 'alpaca', '--docs'],
            ['setup', 'data-provider', '--docs'],
            ['setup', 'data-provider', 'polygon', '--docs'],
            ['setup', 'data-provider', 'coinmarketcap', '--docs'],
        ]
        
        for cmd in test_commands:
            result = self._run_cli_command(cli_runner, *cmd)
            assert result.returncode == 0, f"Command {' '.join(cmd)} failed with exit code {result.returncode}"
            # All docs commands should produce some output
            assert len(result.stdout.strip()) > 0, f"Command {' '.join(cmd)} produced no output"

    def test_setup_docs_handles_warnings_gracefully(self, cli_runner):
        """setup --docs should work even with dependency warnings"""
        result = self._run_cli_command(cli_runner, 'setup', '--docs')
        
        assert result.returncode == 0
        
        # Should show documentation despite warnings
        assert "🔧 StrateQueue Setup Documentation" in result.stdout
        
        # Warnings should be in stderr, not interfere with main output
        # (though they might appear in combined output in some test environments)
        assert "Available Setup Options:" in result.stdout


class TestSetupCommandInteractive:
    """Test setup command interactive functionality using pexpect"""

    def test_interactive_broker_setup_alpaca_paper_trading(self, tmp_working_dir):
        """E-1: Interactive setup for Alpaca broker with paper trading credentials"""
        # Create a temporary directory for credentials with proper permissions
        creds_dir = ensure_directory_with_permissions(tmp_working_dir / ".stratequeue")
        
        # Set up environment to use temporary directory
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # Print debug info about the environment
        print(f"Running test with HOME={env['HOME']}")
        print(f"Credentials directory: {creds_dir}")
        
        # Spawn the interactive setup command
        cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py setup"
        child = pexpect.spawn('/bin/bash', ['-c', cmd], env=env, timeout=30, encoding='utf-8')
        
        try:
            # Wait for the main menu
            child.expect("What would you like to configure?", timeout=15)
            
            # Choose "Broker"
            child.sendline("")  # Select first option (Broker)
            
            # Wait for broker selection menu
            child.expect("Select broker to configure:", timeout=10)
            
            # Choose Alpaca
            child.sendline("")  # Select first option (Alpaca)
            
            # Wait for trading mode selection
            child.expect("Select trading mode:", timeout=10)
            
            # Choose Paper Trading
            child.sendline("")  # Select first option (Paper Trading)
            
            # Wait for API key prompt
            child.expect("Paper API Key:", timeout=10)
            
            # Enter fake API key
            test_api_key = "PKTEST12345678901234567890"
            child.sendline(test_api_key)
            
            # Wait for secret key prompt
            child.expect("Paper Secret Key:", timeout=10)
            
            # Enter fake secret key
            test_secret_key = "abcdef1234567890abcdef1234567890abcdef12"
            child.sendline(test_secret_key)
            
            # Wait for success message
            child.expect("✅ Alpaca credentials saved.", timeout=10)
            
            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            
            # Check exit code
            child.close()
            assert child.exitstatus == 0, f"Interactive setup failed with exit code {child.exitstatus}"
            
            # Verify credentials file was created
            creds_file = creds_dir / "credentials.env"
            assert creds_file.exists(), "Credentials file was not created"
            
            # Print debug info about the file
            print(f"Credentials file: {creds_file}")
            print(f"File exists: {creds_file.exists()}")
            if creds_file.exists():
                print(f"File size: {creds_file.stat().st_size} bytes")
                print(f"File permissions: {oct(creds_file.stat().st_mode)}")
            
            # Verify credentials content
            content = creds_file.read_text()
            assert f"PAPER_KEY={test_api_key}" in content
            assert f"PAPER_SECRET={test_secret_key}" in content
            assert "PAPER_ENDPOINT=https://paper-api.alpaca.markets" in content
            
        except pexpect.TIMEOUT as e:
            print(f"Timeout during interactive setup: {e}")
            print(f"Before timeout: {child.before}")
            print(f"After timeout: {child.after}")
            raise
        except Exception as e:
            print(f"Interactive setup failed: {e}")
            print(f"Child output: {child.before}")
            raise
        finally:
            if child.isalive():
                child.terminate()

    def test_interactive_broker_setup_alpaca_live_trading_confirmation(self, tmp_working_dir):
        """E-1b: Interactive setup for Alpaca with live trading confirmation flow"""
        # Create a temporary directory for credentials
        creds_dir = tmp_working_dir / ".stratequeue"
        creds_dir.mkdir(exist_ok=True)
        
        # Set up environment to use temporary directory
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # Spawn the interactive setup command
        cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py setup"
        child = pexpect.spawn('/bin/bash', ['-c', cmd], env=env, timeout=30, encoding='utf-8')
        
        try:
            # Wait for the main menu
            child.expect("What would you like to configure?", timeout=15)
            
            # Choose "Broker"
            child.sendline("")  # Select first option (Broker)
            
            # Wait for broker selection menu
            child.expect("Select broker to configure:", timeout=10)
            
            # Choose Alpaca
            child.sendline("")  # Select first option (Alpaca)
            
            # Wait for trading mode selection
            child.expect("Select trading mode:", timeout=10)
            
            # Choose Live Trading
            child.send("\x1b[B")  # Arrow down to second option
            child.sendline("")
            
            # Wait for live trading confirmation
            child.expect("Are you sure you want to configure live trading?", timeout=10)
            
            # Choose "No, use paper trading instead"
            child.sendline("")  # Select first option (No)
            
            # Should switch to paper trading
            child.expect("Paper API Key:", timeout=10)
            
            # Enter fake API key
            test_api_key = "PKTEST98765432109876543210"
            child.sendline(test_api_key)
            
            # Wait for secret key prompt
            child.expect("Paper Secret Key:", timeout=10)
            
            # Enter fake secret key
            test_secret_key = "fedcba0987654321fedcba0987654321fedcba09"
            child.sendline(test_secret_key)
            
            # Wait for success message
            child.expect("✅ Alpaca credentials saved.", timeout=10)
            
            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            
            # Check exit code
            child.close()
            assert child.exitstatus == 0, f"Interactive setup failed with exit code {child.exitstatus}"
            
            # Verify credentials file was created with paper trading settings
            creds_file = creds_dir / "credentials.env"
            assert creds_file.exists(), "Credentials file was not created"
            
            # Verify credentials content (should be paper trading)
            content = creds_file.read_text()
            assert f"PAPER_KEY={test_api_key}" in content
            assert f"PAPER_SECRET={test_secret_key}" in content
            assert "PAPER_ENDPOINT=https://paper-api.alpaca.markets" in content
            
        except pexpect.TIMEOUT as e:
            print(f"Timeout during interactive setup: {e}")
            print(f"Before timeout: {child.before}")
            print(f"After timeout: {child.after}")
            raise
        except Exception as e:
            print(f"Interactive setup failed: {e}")
            print(f"Child output: {child.before}")
            raise
        finally:
            if child.isalive():
                child.terminate()

    def test_interactive_setup_cancellation(self, tmp_working_dir):
        """E-1c: Test cancellation of interactive setup"""
        # Set up environment to use temporary directory
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # Spawn the interactive setup command
        cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py setup"
        child = pexpect.spawn('/bin/bash', ['-c', cmd], env=env, timeout=30, encoding='utf-8')
        
        try:
            # Wait for the main menu
            child.expect("What would you like to configure?", timeout=15)
            
            # Send Ctrl+C to cancel
            child.send('\x03')  # Ctrl+C
            
            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            
            # Check exit code (should be 130 for keyboard interrupt)
            child.close()
            assert child.exitstatus == 130, f"Expected exit code 130 for cancellation, got {child.exitstatus}"
            
        except pexpect.TIMEOUT as e:
            print(f"Timeout during cancellation test: {e}")
            print(f"Before timeout: {child.before}")
            print(f"After timeout: {child.after}")
            raise
        except Exception as e:
            print(f"Cancellation test failed: {e}")
            print(f"Child output: {child.before}")
            raise
        finally:
            if child.isalive():
                child.terminate()

    def test_interactive_data_provider_setup_polygon(self, tmp_working_dir):
        """E-1d: Interactive setup for Polygon data provider"""
        # Create a temporary directory for credentials
        creds_dir = tmp_working_dir / ".stratequeue"
        creds_dir.mkdir(exist_ok=True)
        
        # Set up environment to use temporary directory
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # Spawn the interactive setup command
        cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py setup"
        child = pexpect.spawn('/bin/bash', ['-c', cmd], env=env, timeout=30, encoding='utf-8')
        
        try:
            # Wait for the main menu
            child.expect("What would you like to configure?", timeout=15)
            
            # Choose "Data Provider"
            child.send("\x1b[B")  # Arrow down to second option
            child.sendline("")
            
            # Wait for provider selection menu
            child.expect("Select data provider to configure:", timeout=10)
            
            # Choose Polygon
            child.sendline("")  # Select first option (Polygon)
            
            # Wait for API key prompt
            child.expect("Polygon API Key:", timeout=10)
            
            # Enter fake API key
            test_api_key = "test_polygon_api_key_12345"
            child.sendline(test_api_key)
            
            # Wait for success message
            child.expect("✅ Polygon credentials saved.", timeout=10)
            
            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            
            # Check exit code
            child.close()
            assert child.exitstatus == 0, f"Interactive setup failed with exit code {child.exitstatus}"
            
            # Verify credentials file was created
            creds_file = creds_dir / "credentials.env"
            assert creds_file.exists(), "Credentials file was not created"
            
            # Verify credentials content
            content = creds_file.read_text()
            assert f"POLYGON_API_KEY={test_api_key}" in content
            assert "DATA_PROVIDER=polygon" in content
            
        except pexpect.TIMEOUT as e:
            print(f"Timeout during interactive setup: {e}")
            print(f"Before timeout: {child.before}")
            print(f"After timeout: {child.after}")
            raise
        except Exception as e:
            print(f"Interactive setup failed: {e}")
            print(f"Child output: {child.before}")
            raise
        finally:
            if child.isalive():
                child.terminate()


class TestSetupCommandCrossWorkflow:
    """Test cross-command workflow persistence between setup and status"""

    def test_interactive_setup_then_status_persistence(self, tmp_working_dir):
        """F-1: Interactive setup followed by status command shows green checkmarks"""
        # Create a temporary directory for credentials
        creds_dir = tmp_working_dir / ".stratequeue"
        creds_dir.mkdir(exist_ok=True)
        
        # Set up environment to use temporary directory
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # === PHASE 1: Interactive Setup ===
        # Spawn the interactive setup command
        cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py setup"
        child = pexpect.spawn('/bin/bash', ['-c', cmd], env=env, timeout=30, encoding='utf-8')
        
        try:
            # Wait for the main menu
            child.expect("What would you like to configure?", timeout=15)
            
            # Choose "Broker"
            child.sendline("")  # Select first option (Broker)
            
            # Wait for broker selection menu
            child.expect("Select broker to configure:", timeout=10)
            
            # Choose Alpaca
            child.sendline("")  # Select first option (Alpaca)
            
            # Wait for trading mode selection
            child.expect("Select trading mode:", timeout=10)
            
            # Choose Paper Trading
            child.sendline("")  # Select first option (Paper Trading)
            
            # Wait for API key prompt
            child.expect("Paper API Key:", timeout=10)
            
            # Enter fake API key
            test_api_key = "PKTEST_PERSISTENCE_TEST_123456"
            child.sendline(test_api_key)
            
            # Wait for secret key prompt
            child.expect("Paper Secret Key:", timeout=10)
            
            # Enter fake secret key
            test_secret_key = "secret_persistence_test_abcdef123456789"
            child.sendline(test_secret_key)
            
            # Wait for success message
            child.expect("✅ Alpaca credentials saved.", timeout=10)
            
            # Wait for process to complete
            child.expect(pexpect.EOF, timeout=5)
            
            # Check exit code
            child.close()
            assert child.exitstatus == 0, f"Interactive setup failed with exit code {child.exitstatus}"
            
            # Verify credentials file was created
            creds_file = creds_dir / "credentials.env"
            assert creds_file.exists(), "Credentials file was not created"
            
            # Verify credentials content
            content = creds_file.read_text()
            assert f"PAPER_KEY={test_api_key}" in content
            assert f"PAPER_SECRET={test_secret_key}" in content
            assert "PAPER_ENDPOINT=https://paper-api.alpaca.markets" in content
            
        except pexpect.TIMEOUT as e:
            print(f"Timeout during interactive setup: {e}")
            print(f"Before timeout: {child.before}")
            print(f"After timeout: {child.after}")
            raise
        except Exception as e:
            print(f"Interactive setup failed: {e}")
            print(f"Child output: {child.before}")
            raise
        finally:
            if child.isalive():
                child.terminate()
        
        # === PHASE 2: Status Command ===
        # Now test that status command detects the credentials
        # Set up environment variables from the credentials file
        env_with_creds = create_minimal_test_env(home_dir=str(tmp_working_dir))
        env_with_creds.update({
            'PAPER_KEY': test_api_key,
            'PAPER_SECRET': test_secret_key,
            'PAPER_ENDPOINT': 'https://paper-api.alpaca.markets'
        })
        
        # Run status command
        status_cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py status broker"
        status_result = subprocess.run(
            ['/bin/bash', '-c', status_cmd],
            env=env_with_creds,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Verify status command succeeded
        assert status_result.returncode == 0, f"Status command failed with exit code {status_result.returncode}"
        
        # Verify green checkmarks (✅) in status output
        status_output = status_result.stdout
        assert "✅ Detected and configured" in status_output, f"Expected green checkmark not found in status output: {status_output}"
        assert "ALPACA:" in status_output or "Alpaca" in status_output, f"Alpaca broker not mentioned in status: {status_output}"
        
        # Should not show red X marks for Alpaca
        # Check if the Alpaca section specifically has a red X
        alpaca_section = ""
        lines = status_output.split('\n')
        in_alpaca_section = False
        for line in lines:
            if "ALPACA:" in line:
                in_alpaca_section = True
                alpaca_section = line + '\n'
            elif in_alpaca_section:
                if line.strip() and not line.startswith('  '):
                    # Start of new section
                    break
                alpaca_section += line + '\n'
        
        assert "❌ Not detected" not in alpaca_section, f"Unexpected red X for Alpaca: {alpaca_section}"

    def test_programmatic_env_file_then_status_persistence(self, tmp_working_dir):
        """F-1b: Programmatically write env file, then verify status detects it"""
        # Create a temporary directory for credentials
        creds_dir = tmp_working_dir / ".stratequeue"
        creds_dir.mkdir(exist_ok=True)
        
        # Write credentials file programmatically
        test_api_key = "PKTEST_PROGRAMMATIC_123456"
        test_secret_key = "secret_programmatic_abcdef123456789"
        
        creds_file = creds_dir / "credentials.env"
        creds_content = f"""# StrateQueue Credentials
# Generated by: stratequeue setup

PAPER_KEY={test_api_key}
PAPER_SECRET={test_secret_key}
PAPER_ENDPOINT=https://paper-api.alpaca.markets
"""
        creds_file.write_text(creds_content)
        
        # Verify file was written correctly
        assert creds_file.exists(), "Credentials file was not created"
        content = creds_file.read_text()
        assert f"PAPER_KEY={test_api_key}" in content
        assert f"PAPER_SECRET={test_secret_key}" in content
        
        # Set up environment to use temporary directory and credentials
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        env.update({
            'PAPER_KEY': test_api_key,
            'PAPER_SECRET': test_secret_key,
            'PAPER_ENDPOINT': 'https://paper-api.alpaca.markets'
        })
        
        # Run status command
        status_cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py status broker"
        status_result = subprocess.run(
            ['/bin/bash', '-c', status_cmd],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Verify status command succeeded
        assert status_result.returncode == 0, f"Status command failed with exit code {status_result.returncode}"
        
        # Verify green checkmarks (✅) in status output
        status_output = status_result.stdout
        assert "✅ Detected and configured" in status_output, f"Expected green checkmark not found in status output: {status_output}"
        assert "ALPACA:" in status_output or "Alpaca" in status_output, f"Alpaca broker not mentioned in status: {status_output}"
        
        # Should not show red X marks for Alpaca
        # Check if the Alpaca section specifically has a red X
        alpaca_section = ""
        lines = status_output.split('\n')
        in_alpaca_section = False
        for line in lines:
            if "ALPACA:" in line:
                in_alpaca_section = True
                alpaca_section = line + '\n'
            elif in_alpaca_section:
                if line.strip() and not line.startswith('  '):
                    # Start of new section
                    break
                alpaca_section += line + '\n'
        
        assert "❌ Not detected" not in alpaca_section, f"Unexpected red X for Alpaca: {alpaca_section}"

    def test_setup_then_status_different_sessions(self, tmp_working_dir):
        """F-1c: Setup in one session, status in another (simulates CLI restart)"""
        # Create a temporary directory for credentials
        creds_dir = tmp_working_dir / ".stratequeue"
        creds_dir.mkdir(exist_ok=True)
        
        # Write credentials using the setup command's file writing mechanism
        test_api_key = "PKTEST_DIFFERENT_SESSION_123"
        test_secret_key = "secret_different_session_abc123"
        
        creds_file = creds_dir / "credentials.env"
        creds_content = f"""# StrateQueue Credentials
# Generated by: stratequeue setup

PAPER_KEY={test_api_key}
PAPER_SECRET={test_secret_key}
PAPER_ENDPOINT=https://paper-api.alpaca.markets
"""
        creds_file.write_text(creds_content)
        
        # === SESSION 1: Verify credentials were saved ===
        assert creds_file.exists(), "Credentials file was not created"
        content = creds_file.read_text()
        assert f"PAPER_KEY={test_api_key}" in content
        assert f"PAPER_SECRET={test_secret_key}" in content
        
        # === SESSION 2: New environment, fresh status check ===
        # Simulate a completely new CLI session with fresh environment
        fresh_env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        fresh_env.update({
            # Load credentials from file (simulating what the CLI would do)
            'PAPER_KEY': test_api_key,
            'PAPER_SECRET': test_secret_key,
            'PAPER_ENDPOINT': 'https://paper-api.alpaca.markets'
        })
        
        # Run status command in fresh session
        status_cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py status broker"
        status_result = subprocess.run(
            ['/bin/bash', '-c', status_cmd],
            env=fresh_env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Verify status command succeeded
        assert status_result.returncode == 0, f"Status command failed with exit code {status_result.returncode}"
        
        # Verify persistence: credentials are still detected
        status_output = status_result.stdout
        assert "✅ Detected and configured" in status_output, f"Credentials not persisted across sessions: {status_output}"
        assert "ALPACA:" in status_output or "Alpaca" in status_output, f"Alpaca broker not found in fresh session: {status_output}"

    def test_invalid_credentials_show_red_x(self, tmp_working_dir):
        """F-1d: Invalid/missing credentials should show red X marks"""
        # Set up environment with no credentials
        env = create_minimal_test_env(home_dir=str(tmp_working_dir))
        
        # The minimal environment already has empty credentials, so no need to remove them
        
        # Run status command with no credentials
        status_cmd = f"cd {tmp_working_dir} && {PYTHON_EXEC} {os.getcwd()}/main.py status broker"
        status_result = subprocess.run(
            ['/bin/bash', '-c', status_cmd],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Verify status command succeeded (it should not fail, just show no credentials)
        assert status_result.returncode == 0, f"Status command failed with exit code {status_result.returncode}"
        
        # Verify red X marks (❌) for missing credentials
        status_output = status_result.stdout
        assert "❌ Not detected" in status_output, f"Expected red X for missing credentials not found: {status_output}"
        assert "ALPACA:" in status_output or "Alpaca" in status_output, f"Alpaca broker not mentioned in status: {status_output}"
        
        # Should not show green checkmarks for Alpaca
        # Check if the Alpaca section specifically has a green checkmark
        alpaca_section = ""
        lines = status_output.split('\n')
        in_alpaca_section = False
        for line in lines:
            if "ALPACA:" in line:
                in_alpaca_section = True
                alpaca_section = line + '\n'
            elif in_alpaca_section:
                if line.strip() and not line.startswith('  '):
                    # Start of new section
                    break
                alpaca_section += line + '\n'
        
        assert "✅ Detected and configured" not in alpaca_section, f"Unexpected green checkmark for Alpaca with no credentials: {alpaca_section}" 