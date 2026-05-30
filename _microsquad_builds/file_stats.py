
import sys
from collections import Counter

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)

    # Count lines (using splitlines to handle all line endings)
    lines = content.splitlines()
    total_lines = len(lines)

    # Count words (case-insensitive)
    words = content.lower().split()
    total_words = len(words)

    # Count characters (including newlines)
    total_chars = len(content)

    # Most frequent words
    word_counts = Counter(words)
    most_common = word_counts.most_common(5)

    # Output results
    print(f"Total lines: {total_lines}")
    print(f"Total words: {total_words}")
    print(f"Total characters: {total_chars}")
    print("Top 5 most frequent words (case-insensitive):")
    for word, count in most_common:
        print(f"  {word}: {count}")

if __name__ == "__main__":
    main()
