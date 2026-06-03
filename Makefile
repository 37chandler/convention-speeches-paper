PYTHON ?= python3

.PHONY: install parse normalize pronouns

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m spacy download en_core_web_sm

parse:
	@echo "Parsing raw transcripts..."
	$(PYTHON) src/parsers/cspan_parser.py
	$(PYTHON) src/parsers/cspan_2024_parser.py
	$(PYTHON) src/parsers/rev_2020_parser.py
	$(PYTHON) src/parsers/rev_2024_parser.py
	$(PYTHON) src/parsers/cnn_2024_parser.py
	$(PYTHON) src/parsers/youtube_parser.py

normalize:
	@echo "Normalizing and building unified speeches..."
	$(PYTHON) src/normalizer/normalize_speakers_cspan.py
	$(PYTHON) src/normalizer/normalize_speakers_cspan_2024.py
	$(PYTHON) src/normalizer/normalize_speakers_2020_rev.py
	$(PYTHON) src/normalizer/normalize_speakers_2024_rev.py
	$(PYTHON) src/normalizer/normalize_speakers_2024_cnn.py
	$(PYTHON) src/normalizer/merge_2024.py
	$(PYTHON) src/normalizer/truecase_speeches_2004_2016.py
	$(PYTHON) src/normalizer/truecase_speeches_2024.py
	$(PYTHON) src/build_unified_speeches.py

pronouns:
	@echo "Extracting I/we pronoun counts..."
	$(PYTHON) src/build_i_vs_we.py

clean:
	@echo "Removing generated files..."
	rm -f data/processed/parsed/*.csv
	rm -f data/processed/normalized/*.csv
	rm -f data/unified_speeches.csv
	rm -f data/pronoun_counts.csv
	rm -f data/pronoun_counts_rolled.csv