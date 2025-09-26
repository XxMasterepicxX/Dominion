# CitizenServe Permit Scraper - Production Version

Production-ready scraper for CitizenServe permit data using Patchright (undetected Playwright) for stealth automation. Designed for Docker deployment on VPS infrastructure.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Local Testing
```bash
# Clone and setup
git clone --recursive <repository>
cd testing

# Install dependencies
pip install -r requirements.txt
patchright install chromium

# Test scraper
python citizenserve_scraper.py
```

### Docker Deployment (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up --build -d

# Check logs
docker-compose logs -f citizenserve-scraper

# Stop services
docker-compose down
```

## 🏗️ Architecture

### Technology Stack
- **Browser Automation**: Patchright (undetected Playwright replacement)
- **reCAPTCHA Bypass**: BypassV3 (HTTP-based token generation)
- **Data Processing**: pandas + openpyxl for Excel handling
- **Containerization**: Docker with Chrome for production deployment
- **Logging**: structlog for structured production logging

### Stealth Features
- ✅ Passes Cloudflare, Kasada, Akamai detection
- ✅ Chrome fingerprint spoofing
- ✅ reCAPTCHA v3 token bypass
- ✅ Headless operation (Docker-friendly)
- ✅ No local browser dependencies

## 📁 Project Structure

```
testing/
├── citizenserve_scraper.py    # Main scraper class
├── BypassV3/                  # reCAPTCHA bypass module
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container configuration
├── docker-compose.yml         # Production deployment
├── .env.example              # Environment variables template
├── permits_MMDDYYYY_MMDDYYYY.json  # Sample output
└── downloads/                 # Excel file storage (mounted volume)
```

## 🎯 Usage Examples

### Python API
```python
from citizenserve_scraper import CitizenServePermitScraper

# Initialize scraper
scraper = CitizenServePermitScraper(download_dir="./downloads")

# Scrape specific date range
result = scraper.scrape_permits("09/25/2025", "09/25/2025")
print(f"Found {result['total_permits']} permits")

# Scrape today's permits
result = scraper.scrape_today()

# Scrape last week's permits
result = scraper.scrape_date_range(days_back=7)
```

### Command Line
```bash
# Run in Docker
docker-compose run citizenserve-scraper python citizenserve_scraper.py

# Custom date range (modify script)
# Edit main() function in citizenserve_scraper.py
```

## 📊 Output Format

### Excel File
- Direct download from CitizenServe (no parsing errors)
- Complete permit data with all fields
- Filename: `permits_MMDDYYYY_MMDDYYYY.xlsx`

### JSON Structure
```json
{
  "extraction_date": "2025-09-26T00:00:00",
  "source": "citizenserve_patchright_scraper",
  "date_range": {"start": "09/25/2025", "end": "09/25/2025"},
  "total_permits": 30,
  "excel_file": "permits_09252025_09252025.xlsx",
  "permits": [
    {
      "Permit#": "B25-001207",
      "PermitType": "Building Permit",
      "Address": "5091 SW 51ST DR",
      "ApplicationDate": "09/25/2025",
      "Construction Cost": 3500.0
    }
  ]
}
```

## 🔧 Configuration

### Environment Variables
```bash
# Copy and modify
cp .env.example .env

# Key variables
LOG_LEVEL=INFO              # Logging level
DOWNLOAD_DIR=/app/downloads  # Download directory
```

### Docker Resources
Default container limits (adjust for your VPS):
- Memory: 2GB limit, 1GB reserved
- CPU: 1.0 limit, 0.5 reserved

## 🐛 Troubleshooting

### Common Issues

**"Export button not found"**
- Solution: Increase wait time in scraper, check date has permits

**"reCAPTCHA token failed"**
- Solution: BypassV3 dependency issue, check network connectivity

**"Chrome not found in Docker"**
- Solution: Dockerfile installs google-chrome-stable, rebuild image

**Downloads not persisting**
- Solution: Check volume mounts in docker-compose.yml

### Debug Mode
```python
# Enable debug logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(10)  # DEBUG level
)
```

### Health Checks
```bash
# Check container health
docker-compose ps

# View detailed logs
docker-compose logs citizenserve-scraper

# Interactive debugging
docker-compose exec citizenserve-scraper bash
```

## 🚀 Production Deployment

### VPS Setup
```bash
# Install Docker on Oracle VPS
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Deploy scraper
git clone <repository>
cd testing
docker-compose up -d
```

### Monitoring
- Health checks every 30 seconds
- Log rotation (50MB max, 3 files)
- Resource monitoring via Docker stats
- Automatic restart on failure

## 🔒 Security

- Non-root container user
- Network isolation with bridge networks
- No unnecessary privileges
- Secure Chrome sandbox execution
- Environment variable isolation

## 📈 Performance

### Benchmarks (Oracle VPS 2GB RAM)
- Average scrape time: 30-45 seconds
- Memory usage: ~800MB peak
- Success rate: >95% (with proper error handling)
- Concurrent instances: 2-3 max recommended

### Optimization Tips
- Use persistent browser contexts for multiple scrapes
- Implement request caching for repeated operations
- Monitor memory usage and restart containers if needed
- Use proxy rotation for high-frequency scraping

## 📝 Integration

This scraper is designed to integrate with the Dominion Intelligence Platform:

```python
# src/scrapers/sources/citizenserve.py
from testing.citizenserve_scraper import CitizenServePermitScraper

class CitizenServeSource(BaseScraper):
    def __init__(self):
        self.scraper = CitizenServePermitScraper()

    async def daily_scrape(self):
        result = self.scraper.scrape_today()
        return self.process_permits(result['permits'])
```

## 🤝 Contributing

1. Test changes locally with Docker
2. Ensure stealth capabilities remain intact
3. Follow structured logging patterns
4. Update documentation for API changes

## 📄 License

Part of the Dominion Intelligence Platform. See main repository for licensing terms.