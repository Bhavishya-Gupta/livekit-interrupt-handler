"""
Configuration management for LiveKit Interrupt Handler.

Handles environment variables, validation, and default settings.
"""

import os
from typing import List, Dict, Any
from pathlib import Path


class InterruptHandlerConfig:
    """
    Configuration manager for InterruptHandler.
    
    Reads from environment variables and provides validated config dict.
    """
    
    # Default filler words (can be extended)
    DEFAULT_IGNORED_WORDS = [
        'uh', 'um', 'umm', 'hmm', 'hm', 'haan', 'huh',
        'eh', 'ah', 'er', 'mm', 'mhm', 'uh-huh', 'mm-hmm'
    ]
    
    # Default command words (always trigger interrupt)
    DEFAULT_COMMAND_WORDS = [
        'wait', 'stop', 'hold', 'pause', 'no', 'listen',
        'excuse me', 'hang on', 'one second', 'actually'
    ]
    
    # Default thresholds
    DEFAULT_CONFIDENCE_THRESHOLD = 0.3
    DEFAULT_LOW_CONFIDENCE_TIME_MS = 500
    
    def __init__(self):
        """Initialize config from environment variables"""
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Environment Variables:
            IGNORED_WORDS: Comma-separated list of filler words
            COMMAND_WORDS: Comma-separated list of command words
            CONFIDENCE_THRESHOLD: Float between 0 and 1
            LOW_CONFIDENCE_TIME_MS: Integer milliseconds
            LOG_FILE: Path to JSONL log file
            ENABLE_LOGGING: 'true' or 'false'
        
        Returns:
            Dict with validated configuration
        """
        config = {}
        
        # Load ignored words
        ignored_words_env = os.getenv('IGNORED_WORDS', '').strip()
        if ignored_words_env:
            config['ignored_words'] = [
                w.strip() for w in ignored_words_env.split(',') if w.strip()
            ]
        else:
            config['ignored_words'] = self.DEFAULT_IGNORED_WORDS.copy()
        
        # Load command words
        command_words_env = os.getenv('COMMAND_WORDS', '').strip()
        if command_words_env:
            config['command_words'] = [
                w.strip() for w in command_words_env.split(',') if w.strip()
            ]
        else:
            config['command_words'] = self.DEFAULT_COMMAND_WORDS.copy()
        
        # Load confidence threshold
        confidence_env = os.getenv('CONFIDENCE_THRESHOLD', '').strip()
        if confidence_env:
            try:
                confidence = float(confidence_env)
                if 0 <= confidence <= 1:
                    config['confidence_threshold'] = confidence
                else:
                    raise ValueError("Must be between 0 and 1")
            except ValueError as e:
                print(f"Warning: Invalid CONFIDENCE_THRESHOLD '{confidence_env}': {e}")
                print(f"Using default: {self.DEFAULT_CONFIDENCE_THRESHOLD}")
                config['confidence_threshold'] = self.DEFAULT_CONFIDENCE_THRESHOLD
        else:
            config['confidence_threshold'] = self.DEFAULT_CONFIDENCE_THRESHOLD
        
        # Load low confidence time
        low_conf_time_env = os.getenv('LOW_CONFIDENCE_TIME_MS', '').strip()
        if low_conf_time_env:
            try:
                config['low_confidence_time_ms'] = int(low_conf_time_env)
            except ValueError:
                print(f"Warning: Invalid LOW_CONFIDENCE_TIME_MS '{low_conf_time_env}'")
                print(f"Using default: {self.DEFAULT_LOW_CONFIDENCE_TIME_MS}")
                config['low_confidence_time_ms'] = self.DEFAULT_LOW_CONFIDENCE_TIME_MS
        else:
            config['low_confidence_time_ms'] = self.DEFAULT_LOW_CONFIDENCE_TIME_MS
        
        # Load log file path
        log_file_env = os.getenv('LOG_FILE', '').strip()
        if log_file_env:
            config['log_file'] = log_file_env
        else:
            config['log_file'] = 'logs/interrupts.jsonl'
        
        # Load logging enable flag
        enable_logging_env = os.getenv('ENABLE_LOGGING', 'true').strip().lower()
        config['enable_logging'] = enable_logging_env in ('true', '1', 'yes', 'on')
        
        return config
    
    def get_config(self) -> Dict[str, Any]:
        """Get the configuration dictionary"""
        return self.config.copy()
    
    def print_config(self):
        """Print current configuration to stdout"""
        print("=" * 60)
        print("InterruptHandler Configuration")
        print("=" * 60)
        print(f"Ignored Words ({len(self.config['ignored_words'])}): "
              f"{', '.join(self.config['ignored_words'][:10])}"
              f"{'...' if len(self.config['ignored_words']) > 10 else ''}")
        print(f"Command Words ({len(self.config['command_words'])}): "
              f"{', '.join(self.config['command_words'][:5])}"
              f"{'...' if len(self.config['command_words']) > 5 else ''}")
        print(f"Confidence Threshold: {self.config['confidence_threshold']}")
        print(f"Low Confidence Time: {self.config['low_confidence_time_ms']}ms")
        print(f"Log File: {self.config['log_file']}")
        print(f"Logging Enabled: {self.config['enable_logging']}")
        print("=" * 60)


def load_config() -> Dict[str, Any]:
    """
    Convenience function to load configuration.
    
    Returns:
        Dict with configuration ready for InterruptHandler
    """
    config_manager = InterruptHandlerConfig()
    return config_manager.get_config()


if __name__ == "__main__":
    # Demo: Print current configuration
    config_manager = InterruptHandlerConfig()
    config_manager.print_config()
