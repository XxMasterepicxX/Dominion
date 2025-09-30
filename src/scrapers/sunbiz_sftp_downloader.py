"""
Florida Sunbiz SFTP Downloader

Downloads daily corporate formation data files from Florida Division of Corporations.
Official public data source - no bot detection, reliable, complete.
"""
import paramiko
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import structlog

logger = structlog.get_logger("dominion.scrapers.sunbiz_sftp")


class SunbizSFTPDownloader:
    """Downloads daily corporate/LLC filing data from Florida Sunbiz SFTP server."""

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        host: str = "sftp.floridados.gov",
        username: str = "Public",
        password: str = "PubAccess1845!"
    ):
        """
        Initialize SFTP downloader.

        Args:
            download_dir: Local directory for downloaded files
            host: SFTP server hostname
            username: SFTP username
            password: SFTP password
        """
        self.host = host
        self.username = username
        self.password = password

        self.download_dir = download_dir or Path("./data/sunbiz")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.base_path = "/Public/doc/cor/"

    def _connect(self) -> tuple:
        """Establish SFTP connection."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30
            )

            sftp = ssh.open_sftp()
            logger.info("SFTP connection established", host=self.host)

            return ssh, sftp

        except Exception as e:
            logger.error("SFTP connection failed", error=str(e))
            raise

    def list_available_files(self) -> List[str]:
        """List all available daily corporate files."""
        ssh, sftp = self._connect()

        try:
            files = sftp.listdir(self.base_path)

            # Filter for daily corporate files (format: YYYYMMDDc.txt)
            daily_files = [
                f for f in files
                if f.endswith('c.txt') and f[0].isdigit() and len(f) == 13
            ]

            daily_files.sort(reverse=True)  # Most recent first

            logger.info(
                "Listed available files",
                total_files=len(daily_files),
                most_recent=daily_files[0] if daily_files else None
            )

            return daily_files

        finally:
            sftp.close()
            ssh.close()

    def download_file(self, filename: str) -> Path:
        """
        Download a specific file.

        Args:
            filename: Filename to download (e.g., "20250929c.txt")

        Returns:
            Path to downloaded file

        Raises:
            FileNotFoundError: If file doesn't exist on server
        """
        ssh, sftp = self._connect()

        try:
            remote_path = f"{self.base_path}{filename}"
            local_path = self.download_dir / filename

            logger.info("Downloading file", remote_path=remote_path)

            sftp.get(remote_path, str(local_path))

            file_size = local_path.stat().st_size

            logger.info(
                "File downloaded",
                filename=filename,
                size_bytes=file_size,
                size_kb=f"{file_size/1024:.1f}"
            )

            return local_path

        finally:
            sftp.close()
            ssh.close()

    def download_date(self, date: datetime) -> Optional[Path]:
        """
        Download corporate filings for a specific date.

        Args:
            date: Date to download (will use YYYYMMDD format)

        Returns:
            Path to downloaded file, or None if file doesn't exist

        Note:
            Files are typically published the day after (e.g., Sept 29 data
            available Sept 30). Weekend/holiday dates won't have files.
        """
        filename = f"{date.strftime('%Y%m%d')}c.txt"

        try:
            return self.download_file(filename)
        except FileNotFoundError:
            logger.warning(
                "File not found for date",
                date=date.strftime('%Y-%m-%d'),
                filename=filename,
                note="Likely weekend/holiday or not yet published"
            )
            return None

    def download_latest(self, max_days_back: int = 7) -> Optional[Path]:
        """
        Download the most recent available file.

        Args:
            max_days_back: How many days back to search

        Returns:
            Path to downloaded file, or None if none found
        """
        for days_ago in range(1, max_days_back + 1):
            date = datetime.now() - timedelta(days=days_ago)

            try:
                filepath = self.download_date(date)
                if filepath:
                    logger.info(
                        "Downloaded latest file",
                        date=date.strftime('%Y-%m-%d'),
                        days_ago=days_ago
                    )
                    return filepath
            except:
                continue

        logger.error(
            "Could not find any recent files",
            max_days_back=max_days_back
        )
        return None

    def download_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Path]:
        """
        Download multiple files for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of paths to downloaded files (may be fewer than requested
            if some dates don't have files)
        """
        downloaded_files = []

        current_date = start_date
        while current_date <= end_date:
            try:
                filepath = self.download_date(current_date)
                if filepath:
                    downloaded_files.append(filepath)
            except Exception as e:
                logger.warning(
                    "Failed to download date",
                    date=current_date.strftime('%Y-%m-%d'),
                    error=str(e)
                )

            current_date += timedelta(days=1)

        logger.info(
            "Downloaded date range",
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            files_downloaded=len(downloaded_files)
        )

        return downloaded_files

    def download_last_n_days(self, days: int = 7) -> List[Path]:
        """
        Download files for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of downloaded file paths
        """
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=days - 1)

        return self.download_date_range(start_date, end_date)

    def get_file_info(self, filename: str) -> dict:
        """
        Get metadata about a file without downloading it.

        Args:
            filename: Filename to check

        Returns:
            Dict with file info (size, modified time)
        """
        ssh, sftp = self._connect()

        try:
            remote_path = f"{self.base_path}{filename}"
            stats = sftp.stat(remote_path)

            return {
                'filename': filename,
                'size_bytes': stats.st_size,
                'size_kb': stats.st_size / 1024,
                'modified': datetime.fromtimestamp(stats.st_mtime)
            }

        finally:
            sftp.close()
            ssh.close()


# Convenience functions for quick access
def download_latest() -> Optional[Path]:
    """Quick function to download latest file."""
    downloader = SunbizSFTPDownloader()
    return downloader.download_latest()


def download_yesterday() -> Optional[Path]:
    """Download yesterday's filings."""
    downloader = SunbizSFTPDownloader()
    yesterday = datetime.now() - timedelta(days=1)
    return downloader.download_date(yesterday)


def download_last_week() -> List[Path]:
    """Download last 7 days of filings."""
    downloader = SunbizSFTPDownloader()
    return downloader.download_last_n_days(7)