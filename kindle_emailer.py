#!/usr/bin/env python3
"""
Send books to Kindle via email
Supports Gmail, Outlook, and other SMTP providers
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional
import json
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email configuration"""
    smtp_server: str
    smtp_port: int
    sender_email: str
    sender_password: str
    kindle_email: str
    use_tls: bool = True


# Common SMTP configurations
SMTP_CONFIGS = {
    'gmail': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True
    },
    'outlook': {
        'smtp_server': 'smtp-mail.outlook.com',
        'smtp_port': 587,
        'use_tls': True
    },
    'yahoo': {
        'smtp_server': 'smtp.mail.yahoo.com',
        'smtp_port': 587,
        'use_tls': True
    }
}


class KindleEmailer:
    """Send books to Kindle via email"""
    
    MAX_FILE_SIZE_MB = 50  # Kindle email attachment limit
    
    def __init__(self, config: EmailConfig):
        self.config = config
    
    @classmethod
    def from_config_file(cls, config_path: str = "email_config.json"):
        """Load configuration from JSON file"""
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Merge with SMTP defaults if provider specified
            provider = config_data.get('provider')
            if provider and provider in SMTP_CONFIGS:
                config_data.update(SMTP_CONFIGS[provider])
            
            return cls(EmailConfig(**config_data))
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            logger.info("Create email_config.json with your settings")
            return None
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None
    
    @classmethod
    def create_config_template(cls, output_path: str = "email_config.json"):
        """Create a configuration template"""
        template = {
            "provider": "gmail",
            "sender_email": "your-email@gmail.com",
            "sender_password": "your-app-password",
            "kindle_email": "your-kindle@kindle.com",
            "_comment": "For Gmail, use an App Password. Find your Kindle email in Amazon account settings."
        }
        
        with open(output_path, 'w') as f:
            json.dump(template, f, indent=2)
        
        logger.info(f"Config template created: {output_path}")
        logger.info("Edit the file with your credentials")
    
    def check_file_size(self, file_path: Path) -> bool:
        """Check if file is within Kindle email size limit"""
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.MAX_FILE_SIZE_MB:
            logger.warning(f"File too large: {file_path.name} ({size_mb:.1f}MB > {self.MAX_FILE_SIZE_MB}MB)")
            return False
        return True
    
    def send_book(self, file_path: Path, subject: str = "Book") -> bool:
        """Send a single book to Kindle"""
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        if not self.check_file_size(file_path):
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.sender_email
            msg['To'] = self.config.kindle_email
            msg['Subject'] = subject
            
            # Attach file
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename={file_path.name}'
            )
            msg.attach(part)
            
            # Send email
            logger.info(f"Sending {file_path.name} to {self.config.kindle_email}")
            
            if self.config.use_tls:
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port)
            
            server.login(self.config.sender_email, self.config.sender_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✓ Sent: {file_path.name}")
            return True
        
        except smtplib.SMTPAuthenticationError:
            logger.error("Authentication failed. Check your email/password")
            logger.info("For Gmail, you need to use an App Password: https://myaccount.google.com/apppasswords")
            return False
        except Exception as e:
            logger.error(f"✗ Failed to send {file_path.name}: {e}")
            return False
    
    def send_books(self, file_paths: List[Path], batch_size: int = 1) -> int:
        """Send multiple books (respects daily Kindle email limits)"""
        sent_count = 0
        
        for i, file_path in enumerate(file_paths, 1):
            logger.info(f"[{i}/{len(file_paths)}]")
            
            if self.send_book(file_path):
                sent_count += 1
            
            # Rate limiting (don't spam Kindle)
            if i % batch_size == 0 and i < len(file_paths):
                logger.info("Waiting 60s to respect rate limits...")
                import time
                time.sleep(60)
        
        return sent_count


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Send books to Kindle via email")
    parser.add_argument('files', nargs='+', help='Book file(s) to send')
    parser.add_argument('-c', '--config', default='email_config.json',
                       help='Path to email config file')
    parser.add_argument('--create-config', action='store_true',
                       help='Create a config template')
    parser.add_argument('-b', '--batch-size', type=int, default=1,
                       help='Number of books to send before pausing')
    
    args = parser.parse_args()
    
    if args.create_config:
        KindleEmailer.create_config_template(args.config)
        return
    
    # Load emailer
    emailer = KindleEmailer.from_config_file(args.config)
    if not emailer:
        return
    
    # Get file paths
    files = [Path(f) for f in args.files]
    
    # Filter for supported formats
    supported = ['.mobi', '.pdf', '.epub', '.azw', '.txt', '.doc', '.docx']
    files = [f for f in files if f.suffix.lower() in supported]
    
    if not files:
        logger.error("No supported book files found")
        logger.info(f"Supported formats: {', '.join(supported)}")
        return
    
    logger.info(f"Found {len(files)} book(s) to send")
    
    # Send books
    sent = emailer.send_books(files, batch_size=args.batch_size)
    logger.info(f"\nSuccessfully sent {sent}/{len(files)} books")


if __name__ == "__main__":
    main()
