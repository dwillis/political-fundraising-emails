#!/usr/bin/env python3
"""
Script to convert emails_with_body.csv to JSON format.
"""

import csv
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Increase CSV field size limit to handle large email bodies
csv.field_size_limit(sys.maxsize)


def parse_date_components(row: Dict[str, str]) -> Optional[str]:
    """
    Parse date components from CSV row and return ISO format date string.
    
    Args:
        row: Dictionary containing CSV row data
        
    Returns:
        ISO format date string or None if date parsing fails
    """
    try:
        if row['date'] and row['date'] != 'None':
            # Use the full date string if available
            return row['date']
        elif all(row[field] and row[field] != 'None' for field in ['year', 'month', 'day', 'hour', 'minute']):
            # Construct date from components
            year = int(row['year'])
            month = int(row['month'])
            day = int(row['day'])
            hour = int(row['hour'])
            minute = int(row['minute'])
            
            dt = datetime(year, month, day, hour, minute)
            return dt.isoformat()
        else:
            return None
    except (ValueError, TypeError):
        return None


def convert_row_to_dict(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Convert a CSV row to a properly typed dictionary.
    
    Args:
        row: Dictionary containing CSV row data
        
    Returns:
        Dictionary with properly typed values
    """
    # Parse boolean disclaimer field
    disclaimer = None
    if row['disclaimer'] and row['disclaimer'] != 'None':
        disclaimer = row['disclaimer'].lower() == 'true'
    
    # Parse date
    date_str = parse_date_components(row)
    
    # Create the email dictionary
    email_data = {
        'sender': {
            'name': row['name'] if row['name'] and row['name'] != 'None' else None,
            'email': row['email'] if row['email'] and row['email'] != 'None' else None
        },
        'subject': row['subject'] if row['subject'] and row['subject'] != 'None' else None,
        'date': date_str,
        'domain': row['domain'] if row['domain'] and row['domain'] != 'None' else None,
        'body': row['body'] if row['body'] and row['body'] != 'None' else None,
        'party': row['party'] if row['party'] and row['party'] != 'None' else None,
        'disclaimer': disclaimer
    }
    
    # Add date components if available
    if all(row[field] and row[field] != 'None' for field in ['year', 'month', 'day']):
        email_data['date_components'] = {
            'year': int(row['year']),
            'month': int(row['month']),
            'day': int(row['day']),
            'hour': int(row['hour']) if row['hour'] and row['hour'] != 'None' else None,
            'minute': int(row['minute']) if row['minute'] and row['minute'] != 'None' else None
        }
    
    return email_data


def csv_to_json(csv_file_path: str, json_file_path: str, pretty_print: bool = True) -> None:
    """
    Convert CSV file to JSON format.
    
    Args:
        csv_file_path: Path to input CSV file
        json_file_path: Path to output JSON file
        pretty_print: Whether to format JSON with indentation
    """
    emails = []
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 because of header
                try:
                    email_data = convert_row_to_dict(row)
                    emails.append(email_data)
                except Exception as e:
                    print(f"Warning: Error processing row {row_num}: {e}", file=sys.stderr)
                    continue
        
        # Write JSON output
        with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
            if pretty_print:
                json.dump({
                    'metadata': {
                        'total_emails': len(emails),
                        'generated_at': datetime.now().isoformat(),
                        'source_file': csv_file_path
                    },
                    'emails': emails
                }, jsonfile, indent=2, ensure_ascii=False)
            else:
                json.dump({
                    'metadata': {
                        'total_emails': len(emails),
                        'generated_at': datetime.now().isoformat(),
                        'source_file': csv_file_path
                    },
                    'emails': emails
                }, jsonfile, ensure_ascii=False)
        
        print(f"Successfully converted {len(emails)} emails to {json_file_path}")
        
    except FileNotFoundError:
        print(f"Error: Could not find CSV file: {csv_file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function to handle command line arguments and run conversion."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert emails_with_body.csv to JSON format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_to_json.py
  python csv_to_json.py --input custom_emails.csv --output emails.json
  python csv_to_json.py --compact
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        default='emails_with_body.csv',
        help='Input CSV file path (default: emails_with_body.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='emails_with_body.json',
        help='Output JSON file path (default: emails_with_body.json)'
    )
    
    parser.add_argument(
        '--compact', '-c',
        action='store_true',
        help='Output compact JSON without pretty printing'
    )
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        print("Make sure you have run the mbox_converter.py script first to generate the CSV file.", file=sys.stderr)
        sys.exit(1)
    
    # Convert CSV to JSON
    csv_to_json(args.input, args.output, pretty_print=not args.compact)


if __name__ == '__main__':
    main()
