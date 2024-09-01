import json
import re
import os
from typing import List, Dict, Tuple
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

def load_json_data(file_path: str) -> Dict:
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def extract_clean_english_ssml(data: Dict) -> List[str]:
    return [chunk['cleaned_english_translation'] for chunk in data['chunks']]

def test_english_word(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    for i, ssml in enumerate(ssml_list):
        matches = re.finditer(r'\b(?:E|e)nglish\b', ssml, re.IGNORECASE)
        for match in matches:
            if not is_within_language_tag(ssml, match.start()):
                results.append((i, f"Found '{match.group()}' outside language tags"))
    return results

def is_within_language_tag(ssml: str, position: int) -> bool:
    open_tag = ssml.rfind('<lang', 0, position)
    close_tag = ssml.rfind('</lang>', 0, position)
    return open_tag > close_tag


def test_punctuation(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    for i, ssml in enumerate(ssml_list):
        suspicious_punctuation = re.finditer(r'(</[^>]+>|<[^>]+>)\s*([.,:;])', ssml)
        for match in suspicious_punctuation:
            tag = match.group(1)
            if tag in {"<phoneme>", "</phoneme>", "<lang>", "</lang>"}:
                continue
            results.append((i, f"Suspicious punctuation: '{tag}' followed by '{match.group(2)}'"))
    return results


def test_duplicates(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    seen_lines = set()
    for i, ssml in enumerate(ssml_list):
        lines = re.split(r'(?<=\.|\?|!)\s+', ssml)
        for line in lines:
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            if clean_line in seen_lines:
                results.append((i, f"Possible duplicate: '{clean_line}'"))
            else:
                seen_lines.add(clean_line)
    return results

def test_non_standard_characters_outside_tags(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    non_standard_pattern = re.compile(r'[^\x00-\x7F]+')
    tag_pattern = re.compile(r'<[^>]+>')
    
    for i, ssml in enumerate(ssml_list):
        parts = tag_pattern.split(ssml)
        for j, part in enumerate(parts):
            if j % 2 == 0:
                matches = non_standard_pattern.finditer(part)
                for match in matches:
                    results.append((i, f"Non-standard character(s) found outside tags: '{match.group()}'"))
    return results

def test_speak_tags(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    for i, ssml in enumerate(ssml_list):
        opening_tags = ssml.count("<speak>")
        closing_tags = ssml.count("</speak>")
        
        if opening_tags != 1 or closing_tags != 1:
            results.append((i, f"Incorrect number of <speak> tags. Found {opening_tags} opening and {closing_tags} closing tags."))
        elif ssml.find("<speak>") > ssml.find("</speak>"):
            results.append((i, "Closing </speak> tag appears before opening <speak> tag."))
        elif not ssml.strip().startswith("<speak>") or not ssml.strip().endswith("</speak>"):
            results.append((i, "<speak> tags are not at the start and end of the SSML."))
    
    return results

def remove_ssml_tags(text: str) -> str:
    # Remove all SSML tags, including their content for certain tags
    text = re.sub(r'<\s*sub\s+[^>]*>.*?</\s*sub\s*>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def remove_ssml_tags(text: str) -> str:
    # Remove all SSML tags, including their content for certain tags
    text = re.sub(r'<\s*sub\s+[^>]*>.*?</\s*sub\s*>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def count_words(text: str) -> int:
    # Split on whitespace and punctuation, but keep hyphenated words together
    words = re.findall(r'\b[\w-]+\b', text)
    return len(words)

def get_preview(text: str, word_count: int = 5) -> str:
    words = re.findall(r'\b[\w-]+\b', text)
    preview = ' '.join(words[:word_count])
    return preview + '...' if len(words) > word_count else preview

def test_translation_length(data: Dict, low_threshold: float = 0.95, high_threshold: float = 3.0, debug: bool = False) -> List[Tuple[int, str]]:
    results = []
    for i, chunk in enumerate(data['chunks']):
        latin_text = chunk['original_latin']
        english_text = chunk['cleaned_english_translation']
        
        clean_english_text = remove_ssml_tags(english_text)
        
        latin_words = count_words(latin_text)
        english_words = count_words(clean_english_text)
        
        ratio = english_words / latin_words if latin_words > 0 else float('inf')
        
        if debug or ratio > high_threshold or ratio < low_threshold:
            latin_preview = get_preview(latin_text)
            english_preview = get_preview(clean_english_text)
            
            results.append((i, f"Chunk {i}: {'Debug info' if debug else 'Translation length issue detected'}.\n"
                               f"  Latin words: {latin_words}\n"
                               f"  English words: {english_words}\n"
                               f"  Ratio (English/Latin): {ratio:.2f}\n"
                               f"  Latin preview: {latin_preview}\n"
                               f"  English preview: {english_preview}"))
    
    return results

def test_malformed_closing_tags(data: Dict) -> List[Tuple[int, str]]:
    results = []
    malformed_tag_pattern = re.compile(r'</\s*(\w+)[^>]*[.,:;!?][^>]*>')
    
    for i, chunk in enumerate(data['chunks']):
        if 'cleaned_english_translation' in chunk:
            ssml_content = chunk['cleaned_english_translation']
            matches = malformed_tag_pattern.finditer(ssml_content)
            
            for match in matches:
                tag = match.group(1)
                full_match = match.group(0)
                context = ssml_content[max(0, match.start() - 20):match.end() + 20]
                
                results.append((i, f"Chunk {i}: Malformed closing tag detected: '{full_match}'\n"
                                   f"  Tag: {tag}\n"
                                   f"  Context: ...{context}..."))
    
    return results

def test_misplaced_closing_tags(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    # Regex pattern to find closing tags followed immediately by an opening parenthesis or other punctuation
    misplaced_closing_tag_pattern = re.compile(r'</[^>]+>\s*[(.,:;!?)]')
    
    for i, ssml in enumerate(ssml_list):
        matches = misplaced_closing_tag_pattern.finditer(ssml)
        for match in matches:
            context = ssml[max(0, match.start() - 20):match.end() + 20]
            results.append((i, f"Misplaced closing tag detected: '{match.group(0)}'\n"
                               f"  Context: ...{context}..."))
    
    return results

def test_random_single_letters_outside_tags(ssml_list: List[str]) -> List[Tuple[int, str]]:
    results = []
    # Regex pattern to find single letters that aren't I, A, O, s, or t, and aren't part of SSML tags
    random_single_letter_pattern = re.compile(r'\b(?!I\b|A\b|O\b|s\b|t\b)[B-HJ-NP-Zb-hj-np-z]\b')
    tag_pattern = re.compile(r'<[^>]+>')

    for i, ssml in enumerate(ssml_list):
        # Split the SSML content by tags to isolate text content
        parts = tag_pattern.split(ssml)
        for part in parts:
            if not part.strip():  # Skip empty parts that are just tags
                continue
            matches = random_single_letter_pattern.finditer(part)
            for match in matches:
                context = part[max(0, match.start() - 20):match.end() + 20]
                results.append((i, f"Random single letter detected: '{match.group(0)}'\n"
                                   f"  Context: ...{context}..."))
    
    return results






def run_tests_on_file(file_path: str) -> Dict[str, List[Tuple[int, str]]]:
    data = load_json_data(file_path)
    ssml_list = extract_clean_english_ssml(data)
    
    return {
        "English Word": test_english_word(ssml_list),
        "Punctuation": test_punctuation(ssml_list),
        "Speak Tags": test_speak_tags(ssml_list),
        "Non-standard Characters": test_non_standard_characters_outside_tags(ssml_list),
        "Translation Length": test_translation_length(data),
        "Malformed Closing Tags": test_malformed_closing_tags(data),
        "Misplaced Closing Tags": test_misplaced_closing_tags(ssml_list),
        "Random Single Letters": test_random_single_letters_outside_tags(ssml_list)
    }

def run_tests_on_directory(directory_path: str) -> Dict[str, Dict[str, List[Tuple[int, str]]]]:
    results = {}
    for filename in os.listdir(directory_path):
        if filename.endswith('.json'):
            file_path = os.path.join(directory_path, filename)
            results[filename] = run_tests_on_file(file_path)
    return results

def display_results(results: Dict[str, Dict[str, List[Tuple[int, str]]]]) -> None:
    any_failures = False
    base_url = "http://localhost:5000/view_json/"
    
    for filename, file_results in results.items():
        file_failures = False
        file_output = []
        
        for test_name, test_results in file_results.items():
            if test_results:
                file_failures = True
                any_failures = True
                file_output.append(f"\n  {Fore.YELLOW}{test_name} Test Results:{Style.RESET_ALL}")
                for chunk_index, message in test_results:
                    file_output.append(f"  {Fore.RED}Chunk {chunk_index}:{Style.RESET_ALL} {message}")
        
        if file_failures:
            file_link = f"{base_url}{filename}"
            print(f"\n{Fore.CYAN}Results for {filename}:{Style.RESET_ALL} Open file: {Fore.BLUE}{file_link}{Style.RESET_ALL}")
            print("\n".join(file_output))
            print(f"\n{Fore.YELLOW}{'='*50}{Style.RESET_ALL}")
    
    if not any_failures:
        print(f"\n{Fore.GREEN}All tests passed successfully! No issues found.{Style.RESET_ALL}")


def main():
    print(f"{Fore.CYAN}SSML Test Suite{Style.RESET_ALL}")
    print(f"{Fore.CYAN}================={Style.RESET_ALL}")
    
    while True:
        directory_path = input(f"\nEnter the path to your JSON directory (or 'q' to quit): ").strip()
        
        if directory_path.lower() == 'q':
            print(f"\n{Fore.YELLOW}Thank you for using the SSML Test Suite. Goodbye!{Style.RESET_ALL}")
            break
        
        if not os.path.isdir(directory_path):
            print(f"{Fore.RED}Error: The specified path is not a valid directory. Please try again.{Style.RESET_ALL}")
            continue
        
        print(f"\n{Fore.CYAN}Running tests on files in {directory_path}...{Style.RESET_ALL}")
        results = run_tests_on_directory(directory_path)
        display_results(results)

if __name__ == "__main__":
    main()