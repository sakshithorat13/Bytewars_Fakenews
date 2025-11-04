import json
import re

def clean_json_response(response_text: str) -> str:
    """
    Clean JSON response to extract human-readable text only
    """
    # Remove code blocks
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    
    try:
        # Try to parse as JSON first
        parsed_json = json.loads(response_text)
        
        # Extract meaningful content from JSON
        if isinstance(parsed_json, dict):
            # Extract summary or detailed analysis
            readable_parts = []
            
            for key in ['summary', 'detailed_analysis', 'analysis', 'explanation', 'description']:
                if key in parsed_json and parsed_json[key]:
                    readable_parts.append(str(parsed_json[key]))
            
            # Extract evidence points
            if 'key_evidence_points' in parsed_json and parsed_json['key_evidence_points']:
                evidence = ', '.join(parsed_json['key_evidence_points'])
                readable_parts.append(f"Evidence: {evidence}")
            
            # Extract credibility assessment
            if 'credibility_assessment' in parsed_json and parsed_json['credibility_assessment']:
                readable_parts.append(f"Credibility: {parsed_json['credibility_assessment']}")
            
            return '. '.join(readable_parts) if readable_parts else response_text
        
    except json.JSONDecodeError:
        pass
    
    # If not JSON or parsing failed, clean up the text
    # Remove common JSON artifacts
    cleaned = re.sub(r'\{[^}]*\}', '', response_text)  # Remove JSON objects
    cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)      # Remove JSON arrays
    cleaned = re.sub(r'"[^"]*":', '', cleaned)        # Remove JSON keys
    cleaned = re.sub(r'[:,\{\}\[\]"]', ' ', cleaned)  # Remove JSON punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned)            # Normalize whitespace
    cleaned = cleaned.strip()
    
    return cleaned if cleaned else "Analysis completed."


# Test the function
if __name__ == "__main__":
    test_json = '''
    {
        "verdict": "InsufficientInfo",
        "detailed_analysis": "This claim appears to contradict established scientific evidence about vaccines and safety.",
        "key_evidence_points": ["Multiple peer-reviewed studies", "WHO guidelines"]
    }
    '''
    
    print(clean_json_response(test_json))