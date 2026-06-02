# Political Fundraising Emails

Tools for extracting and comparing political committee names from fundraising emails using local LLMs. Given a JSON file of parsed political emails, these scripts use small language models (via [LLM](https://llm.datasette.io/)) to identify the sponsoring committee from each email's disclaimer, then compare results across models using fuzzy matching.

## Data

The source data file `emails.json` is too large for version control. Download it from [Google Drive](https://drive.google.com/file/d/1Na7iaFA59cPoaiE3n1t3r0PYAAy9Ab0o/view?usp=sharing) and place it in the project root before running.

Each record in `emails.json` contains fields like `email`, `date`, `subject`, `body`, `party`, and `disclaimer`.

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/dwillis/political-fundraising-emails.git
cd political-fundraising-emails
uv sync
```

You also need [Ollama](https://ollama.com/) (or another LLM backend supported by the `llm` CLI) with the models you want to use pulled locally.

## Scripts

### email_add_cmte.py

Runs a local LLM against each email's body text to extract the committee name from political disclaimers. Processes emails in parallel and supports resuming interrupted runs.

```bash
# Process all emails using the default model (qwen3.5:4b)
uv run python email_add_cmte.py emails.json

# Use 8 workers
uv run python email_add_cmte.py emails.json --workers 8

# Test with first 10 emails
uv run python email_add_cmte.py emails.json --test 10
```

Output is written to `emails_updated.json` (derived from the input filename). A `.progress.jsonl` file tracks incremental results so interrupted runs can resume.

To change the model, edit the `model_name` variable at the top of the script. The model must be available through your `llm` installation.

### compare_committees.py

Compares committee extractions across multiple model output files. Reports exact and fuzzy match rates, NA distributions, and samples of disagreements.

```bash
# Compare three model outputs (defaults)
uv run python compare_committees.py

# Specify custom file paths
uv run python compare_committees.py --gemma results_gemma.json --qwen35 results_qwen35.json --qwen3 results_qwen3.json

# Only compare emails with disclaimers
uv run python compare_committees.py --disclaimer

# Export results
uv run python compare_committees.py --export-json stats.json --export-csv disagreements.csv
```

## Dependencies

- **[llm](https://llm.datasette.io/)**: Interface to local and remote language models
- **[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)**: Fast fuzzy string matching for committee name comparison

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Derek Willis
