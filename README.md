# Political Fundraising Emails

A Python toolkit for processing and analyzing political fundraising emails from MBOX format archives. This project extracts, processes, and structures email data to enable analysis of political fundraising patterns and messaging.

## Features

- **MBOX Processing**: Extract emails from MBOX format archives
- **Political Party Classification**: Automatically identify sender political affiliation based on:
  - Domain mappings (800+ pre-mapped political domains)
  - Fundraising platform detection (ActBlue, WinRed, NGP VAN, Anedot)
- **Content Analysis**: Extract and clean email body content with HTML-to-text conversion
- **Metadata Extraction**: Parse sender information, subjects, timestamps, and domains
- **Disclaimer Detection**: Identify emails containing political disclaimers
- **URL Extraction**: Extract and catalog URLs from email content
- **SQLite Integration**: Convert processed data to searchable SQLite database with full-text search

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Make sure you have Python 3.12+ installed.

```bash
# Clone the repository
git clone https://github.com/yourusername/politiical-fundraising-emails.git
cd politiical-fundraising-emails

# Install dependencies
uv sync
```

## Usage

### Basic Processing

1. **Prepare your MBOX file**: Place your MBOX file in an accessible location and update the path in `mbox_converter.py`:

```python
reader = MBoxReader("PATH TO MBOX FILE")  # Update this line
```

2. **Run the processing pipeline**:

```bash
# Execute the full pipeline
./emails.sh
```

Or run steps individually:

```bash
# Process MBOX and generate CSV
python mbox_converter.py

# Create SQLite database with full-text search
sqlite-utils insert emails.db emails emails_with_body.csv --csv
sqlite-utils enable-fts emails.db emails body
```

### Output

The processing generates:

- **`emails_with_body.csv`**: Structured CSV with columns:
  - `name`, `email`: Sender information
  - `subject`, `date`, `year`, `month`, `day`, `hour`, `minute`: Email metadata
  - `domain`: Sender domain
  - `body`: Cleaned email content
  - `party`: Political party affiliation (D/R/None)
  - `disclaimer`: Boolean indicating presence of political disclaimers

- **`emails.db`**: SQLite database with full-text search capabilities

### Political Party Detection

The system identifies political affiliation through multiple methods:

1. **Fundraising Platforms**:
   - ActBlue, NGP VAN → Democratic (D)
   - WinRed, Anedot → Republican (R)

2. **Domain Mapping**: Uses `domain_party_mapping.csv` with 800+ known political domains

3. **Manual Classification**: Update `domain_party_mapping.csv` to add new domain mappings

## Dependencies

- **emailnetwork**: Email processing and metadata extraction
- **html2text**: HTML-to-text conversion
- **mailbox**: MBOX file handling
- **sqlite-utils**: SQLite database operations
- **urlextract**: URL extraction from text

## Data Structure

### CSV Output Schema

| Column | Type | Description |
|--------|------|-------------|
| name | string | Sender name |
| email | string | Sender email address |
| subject | string | Email subject line |
| date | datetime | Full timestamp |
| year/month/day/hour/minute | int | Parsed date components |
| domain | string | Sender domain |
| body | string | Cleaned email content |
| party | string | Political affiliation (D/R/None) |
| disclaimer | boolean | Contains political disclaimer |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Derek Willis

## Acknowledgments

Built with the [emailnetwork](https://pypi.org/project/emailnetwork/) library for email processing and [sqlite-utils](https://sqlite-utils.datasette.io/en/stable/)
