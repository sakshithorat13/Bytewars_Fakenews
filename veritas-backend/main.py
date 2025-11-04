from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import uvicorn
import requests
import base64
import io
from bs4 import BeautifulSoup
from PIL import Image
import json
import os
import re
import time
from collections import defaultdict
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# JSON cleaning utility
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

# Configure APIs
hf_api_key = os.getenv("HF_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    print("Warning: GEMINI_API_KEY not found. Please add it to .env file.")
    raise ValueError("GEMINI_API_KEY is required")

# Configure Google Gemini
genai.configure(api_key=gemini_api_key)

# Simple rate limiting
import time
from collections import defaultdict

# Track request times per IP
request_times = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 1 minute
MAX_REQUESTS_PER_WINDOW = 10  # 10 requests per minute per IP

def check_rate_limit(client_ip: str) -> bool:
    """Check if client is within rate limits"""
    now = time.time()
    
    # Clean old requests
    request_times[client_ip] = [req_time for req_time in request_times[client_ip] 
                               if now - req_time < RATE_LIMIT_WINDOW]
    
    # Check if under limit
    if len(request_times[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
        return False
    
    # Add current request
    request_times[client_ip].append(now)
    return True

# Define models
FACT_CHECK_MODEL = "gemini-2.0-flash-exp"  # For fact-checking and text analysis
IMAGE_MODEL = "gemini-2.0-flash-exp"  # For image processing
SUMMARIZATION_MODEL = "facebook/bart-large-cnn"  # Keeping HF for summarization fallback

# Define unified Hugging Face API query function (for fallback use)
async def query_hf_model(model_id: str, payload: dict) -> dict:
    """
    Unified function to call Hugging Face Inference API (fallback only)
    """
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {hf_api_key}"} if hf_api_key else {}
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ HuggingFace API error: {e}")
        raise HTTPException(status_code=500, detail=f"HuggingFace API error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Gemini API helper functions
import time
import asyncio
from typing import Optional

async def query_gemini_text(prompt: str, model_name: str = FACT_CHECK_MODEL, temperature: float = 0.3, max_retries: int = 3) -> str:
    """
    Query Gemini for text generation and analysis with rate limiting and retry logic
    """
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(model_name)
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=2000,
                top_p=0.8,
                top_k=40
            )
            
            response = model.generate_content(prompt, generation_config=generation_config)
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "429" in error_str or "resource exhausted" in error_str or "quota" in error_str:
                wait_time = (2 ** attempt) * 2  # Exponential backoff: 2, 4, 8 seconds
                print(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print("❌ Max retries exceeded for rate limiting")
                    # Fallback to a simple analysis
                    return await _create_fallback_analysis(prompt)
            else:
                print(f"❌ Gemini API error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    # Fallback for other errors
                    return await _create_fallback_analysis(prompt)
    
    # Should not reach here, but just in case
    return await _create_fallback_analysis(prompt)

async def _create_fallback_analysis(prompt: str) -> str:
    """
    Create a simple fallback analysis when Gemini API is unavailable
    """
    print("🔄 Using fallback analysis due to API limitations")
    
    # Extract the claim from the prompt if possible
    claim_text = ""
    if "Claim:" in prompt:
        lines = prompt.split('\n')
        for line in lines:
            if line.strip().startswith("Claim:"):
                claim_text = line.replace("Claim:", "").strip()
                break
    
    if not claim_text:
        claim_text = prompt[:200] + "..." if len(prompt) > 200 else prompt
    
    # Simple keyword-based analysis
    claim_lower = claim_text.lower()
    
    # Known false claim indicators
    false_indicators = [
        'flat earth', 'earth is flat', 'vaccines cause autism', 'microchips in vaccines',
        '5g causes cancer', 'moon landing fake', 'chemtrails', 'nasa hiding'
    ]
    
    # Known true claim indicators  
    true_indicators = [
        'water boils at 100', 'paris capital france', 'earth round', 'vaccines prevent disease'
    ]
    
    verdict = "InsufficientInfo"
    confidence = 0.5
    analysis = "Limited analysis due to API constraints. "
    
    if any(indicator in claim_lower for indicator in false_indicators):
        verdict = "Contradicted"
        confidence = 0.8
        analysis += "This appears to be a commonly debunked claim."
    elif any(indicator in claim_lower for indicator in true_indicators):
        verdict = "Supported"
        confidence = 0.8
        analysis += "This appears to be a well-established fact."
    else:
        analysis += "Unable to verify due to API limitations."
    
    # Return in JSON format expected by the calling function
    return f'''{{
        "verdict": "{verdict}",
        "confidence_score": {confidence},
        "detailed_analysis": "{analysis}",
        "search_suggestions": ["verify {claim_text[:30]}", "fact check {claim_text[:30]}"],
        "key_evidence_points": ["Analysis limited due to API constraints"],
        "credibility_assessment": "Limited assessment available",
        "context_factors": "API rate limiting prevented full analysis"
    }}'''

async def query_gemini_vision(prompt: str, image_data: bytes, model_name: str = IMAGE_MODEL, max_retries: int = 3) -> str:
    """
    Query Gemini for image analysis with vision capabilities and rate limiting
    """
    for attempt in range(max_retries):
        try:
            # Convert bytes to PIL Image for Gemini
            image = Image.open(io.BytesIO(image_data))
            
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, image])
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "429" in error_str or "resource exhausted" in error_str or "quota" in error_str:
                wait_time = (2 ** attempt) * 2  # Exponential backoff: 2, 4, 8 seconds
                print(f"⚠️ Vision API rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print("❌ Max retries exceeded for vision API")
                    return _create_fallback_vision_analysis()
            else:
                print(f"❌ Gemini Vision API error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    return _create_fallback_vision_analysis()
    
    return _create_fallback_vision_analysis()

def _create_fallback_vision_analysis() -> str:
    """Create fallback analysis for image processing when API is unavailable"""
    return '''{{
        "image_description": "Image analysis unavailable due to API constraints",
        "claims_detected": ["Unable to analyze image content"],
        "potential_issues": ["API rate limiting prevented analysis"],
        "credibility_indicators": "Limited assessment available",
        "recommendation": "Please try again later when API quota is restored"
    }}'''

# Pydantic Data Models
class AnalysisRequest(BaseModel):
    inputType: Literal["text", "url", "image"] = Field(alias="type")
    data: str

class ClaimAnalysis(BaseModel):
    claim: str
    verdict: Literal["Contradicted", "Supported", "InsufficientInfo"]
    explanation: str

class AnalysisResponse(BaseModel):
    score: int
    overallVerdict: str
    summary: str
    breakdown: List[ClaimAnalysis]
    context: Optional[str] = None

app = FastAPI(title="Veritas Backend", version="1.0.0")

# Add CORS middleware with permissive settings for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "Veritas API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "veritas-backend"}

@app.get("/favicon.ico")
async def favicon():
    """Handle favicon requests to prevent 404 errors"""
    return Response(status_code=204)

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request_data: AnalysisRequest, request: Request):
    """Main endpoint to analyze content for fact-checking"""
    print("--- 🚀 NEW REQUEST RECEIVED ---")
    print(f"Input Type: {request_data.inputType}")
    print(f"Data Snippet: {request_data.data[:100]}")

    # Rate limiting check
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        print(f"⚠️ Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. Please wait a moment before making another request. Maximum 10 requests per minute."
        )

    extracted_text = ""
    context = ""

    try:
        if request_data.inputType == "text":
            print("Processing as TEXT...")
            extracted_text = request_data.data
            context = "Input was a raw text message."
        
        elif request_data.inputType == "url":
            print("Processing as URL...")
            extracted_text, context = await process_url_input(request_data.data)
        
        elif request_data.inputType == "image":
            print("Processing as IMAGE...")
            extracted_text, context = await process_image_input(request_data.data)

        print(f"Text Extracted: {extracted_text[:200]}")

        if not extracted_text:
            print("🚨 ERROR: No text was extracted.")
            raise HTTPException(status_code=400, detail="Could not extract any text from the provided input.")

        print("✅ Calling fact-checking engine...")
        result = await run_fact_checking_engine(extracted_text, context)
        print("🎉 Engine finished. Returning final report.")
        return result

    except Exception as e:
        print(f"🔥 ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

# Input Processing Pipelines
async def process_url_input(url: str) -> tuple[str, str]:
    """Process URL input to extract main article text with proper headers"""
    try:
        # Use proper headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print(f"🌐 Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        print(f"✅ Successfully fetched URL (Status: {response.status_code})")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, and navigation elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()
        
        # Remove common ad and menu classes
        for element in soup.find_all(class_=['ad', 'advertisement', 'menu', 'sidebar', 'navigation']):
            element.decompose()
        
        # Try multiple strategies to find main content
        main_content = None
        
        # Strategy 1: Look for main content tags
        for tag in ['main', 'article', '[role="main"]']:
            main_content = soup.select_one(tag)
            if main_content:
                print(f"✅ Found content using strategy: {tag}")
                break
        
        # Strategy 2: Look for content-specific classes
        if not main_content:
            content_selectors = [
                '.mw-parser-output',  # Wikipedia
                '.content',
                '.post-content',
                '.article-content',
                '.entry-content',
                '#content',
                '.main-content'
            ]
            
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    print(f"✅ Found content using selector: {selector}")
                    break
        
        # Strategy 3: Find largest text block
        if not main_content:
            print("⚠️ Using fallback: finding largest text block")
            all_divs = soup.find_all('div')
            if all_divs:
                main_content = max(all_divs, key=lambda div: len(div.get_text(strip=True)))
        
        # Extract text
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            print("⚠️ Using body text as fallback")
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean and limit text
        cleaned_text = ' '.join(text.split())
        
        # Limit text to reasonable size for processing (first 3000 words)
        words = cleaned_text.split()
        if len(words) > 3000:
            cleaned_text = ' '.join(words[:3000]) + "..."
            print(f"⚠️ Text truncated to 3000 words for processing")
        
        context = f"Content extracted from: {url}"
        
        print(f"✅ Extracted {len(words)} words from URL")
        return cleaned_text, context
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=400, detail=f"Request timeout while fetching URL: {url}")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=400, detail=f"Connection error while fetching URL: {url}")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"HTTP error {e.response.status_code} while fetching URL: {url}")
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")

async def process_image_input(data: str) -> tuple[str, str]:
    """Process base64 image input to extract text and context using Gemini Vision"""
    try:
        # 1. Decode the base64 string into image bytes
        image_data = base64.b64decode(data)
        
        # 2. Use Gemini Vision for comprehensive image analysis
        vision_prompt = """
        Analyze this image comprehensively:
        
        1. Describe what you see in the image (objects, people, text, setting, etc.)
        2. Extract any text visible in the image (OCR)
        3. Identify any factual claims or statements that could be fact-checked
        
        Return your response in this JSON format:
        {
            "description": "Detailed description of the image",
            "extracted_text": "Any text found in the image",
            "factual_claims": "Any claims that can be fact-checked"
        }
        """
        
        gemini_response = await query_gemini_vision(vision_prompt, image_data)
        print(f"✅ Gemini Vision response: {gemini_response}")
        
        # Parse the JSON response from Gemini
        try:
            import re
            json_match = re.search(r'\{.*\}', gemini_response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                description = result_data.get("description", "Image analysis completed")
                extracted_text = result_data.get("extracted_text", "No text found in image")
                factual_claims = result_data.get("factual_claims", "")
                
                # Combine extracted text and factual claims
                full_text = f"{extracted_text}. {factual_claims}".strip()
                context = f"Image description: {description}"
                
                return full_text, context
            else:
                # If no JSON, treat the whole response as extracted text
                return gemini_response, "Image analysis completed using Gemini Vision"
        except (json.JSONDecodeError, ValueError):
            # Fallback: treat the response as extracted content
            return gemini_response, "Image analysis completed using Gemini Vision"
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

# Core Fact-Checking Engine
async def run_fact_checking_engine(text_to_analyze: str, initial_context: str) -> AnalysisResponse:
    """Main multi-step fact-checking logic using Gemini 2.5 Flash"""
    
    print("🔍 STARTING FACT-CHECKING ENGINE...")
    print(f"Text to analyze: {text_to_analyze[:100]}...")
    
    try:
        # 1. Extract claims using Gemini 2.5 Flash
        print("📝 Step 1: Extracting claims using Gemini 2.5 Flash...")
        
        extraction_prompt = f"""
        Analyze the following text and extract the main factual claims that can be fact-checked.
        
        Text: {text_to_analyze}
        
        Please respond with a JSON object containing:
        {{
            "claims": [
                "claim 1 text",
                "claim 2 text",
                "claim 3 text"
            ],
            "total_claims": number
        }}
        
        Extract 2-5 specific, factual claims that can be verified. Focus on statements that make assertions about facts, statistics, events, or verifiable information.
        """
        
        claims_response = await query_gemini_text(extraction_prompt, temperature=0.3)
        
        # Parse claims from Gemini response
        try:
            import json
            claims_data = json.loads(claims_response)
            claims = claims_data.get("claims", [])
            
            # Validate and clean claims
            claims = [claim for claim in claims if isinstance(claim, str) and len(claim.strip()) > 10]
            
            if not claims:
                # Fallback: split text into meaningful sentences
                sentences = [s.strip() for s in text_to_analyze.split('.') if s.strip() and len(s.strip()) > 20]
                claims = sentences[:3] if sentences else [text_to_analyze[:200]]
                
                # Add a helpful explanation for insufficient claims
                if len(claims) == 0 or (len(claims) == 1 and len(claims[0]) < 50):
                    claims = ["The provided content may be too brief or lack specific factual claims that can be verified."]
                
            print(f"✅ Claims extracted: {claims}")
            
        except json.JSONDecodeError:
            print("⚠️ JSON parsing failed, using fallback claim extraction")
            sentences = [s.strip() for s in text_to_analyze.split('.') if s.strip() and len(s.strip()) > 20]
            claims = sentences[:3] if sentences else [text_to_analyze[:200]]
        
        # 2. Process each claim with comprehensive fact-checking
        print(f"🔍 Step 2: Processing {len(claims)} claims...")
        verified_breakdown = []
        
        for i, claim in enumerate(claims):
            print(f"🔍 Processing claim {i+1}/{len(claims)}: {claim[:50]}...")
            
            # Comprehensive fact-checking using Gemini 2.5 Flash
            fact_check_prompt = f"""
            Perform a comprehensive fact-check analysis of the following claim:
            
            Claim: {claim}
            
            Please analyze this claim thoroughly and respond with a JSON object:
            {{
                "verdict": "Supported|Contradicted|InsufficientInfo|Mixed",
                "confidence_score": 0.0-1.0,
                "detailed_analysis": "detailed explanation of your analysis",
                "search_suggestions": ["keyword 1", "keyword 2", "keyword 3"],
                "key_evidence_points": [
                    "evidence point 1",
                    "evidence point 2"
                ],
                "credibility_assessment": "assessment of claim's inherent credibility",
                "context_factors": "relevant context that affects verification"
            }}
            
            Guidelines:
            - "Supported": The claim is factually accurate based on available evidence
            - "Contradicted": The claim is factually incorrect or misleading  
            - "InsufficientInfo": Not enough reliable information to verify
            - "Mixed": The claim contains both accurate and inaccurate elements
            
            Consider:
            - Source credibility patterns
            - Historical precedent 
            - Logical consistency
            - Available evidence patterns
            - Common misinformation indicators
            """
            
            try:
                fact_check_response = await query_gemini_text(fact_check_prompt, temperature=0.2)
                
                # Parse the comprehensive analysis
                try:
                    analysis_data = json.loads(fact_check_response)
                    
                    verdict = analysis_data.get("verdict", "InsufficientInfo")
                    confidence = float(analysis_data.get("confidence_score", 0.5))
                    detailed_analysis = analysis_data.get("detailed_analysis", "No analysis available")
                    evidence_points = analysis_data.get("key_evidence_points", [])
                    credibility = analysis_data.get("credibility_assessment", "")
                    
                    explanation = f"Analysis: {detailed_analysis[:200]}"
                    if evidence_points:
                        explanation += f" | Evidence: {'; '.join(evidence_points[:2])}"
                    if credibility:
                        explanation += f" | Credibility: {credibility[:100]}"
                    
                except json.JSONDecodeError:
                    print(f"⚠️ JSON parsing failed for claim {i+1}, using text analysis")
                    
                    # Fallback text analysis
                    response_lower = fact_check_response.lower()
                    
                    if any(word in response_lower for word in ['false', 'incorrect', 'misleading', 'contradicted']):
                        verdict = "Contradicted"
                        confidence = 0.7
                    elif any(word in response_lower for word in ['true', 'accurate', 'supported', 'verified']):
                        verdict = "Supported" 
                        confidence = 0.7
                    else:
                        verdict = "InsufficientInfo"
                        confidence = 0.5
                    
                    explanation = clean_json_response(fact_check_response)
                
                verified_breakdown.append(ClaimAnalysis(
                    claim=claim,
                    verdict=verdict,
                    explanation=explanation
                ))
                
            except Exception as e:
                print(f"⚠️ Error processing claim {i+1}: {str(e)}")
                verified_breakdown.append(ClaimAnalysis(
                    claim=claim,
                    verdict="InsufficientInfo",
                    explanation=f"Error during analysis: {str(e)}"
                ))
        
        # 3. Synthesize final report using Gemini
        print("📊 Step 3: Synthesizing final report...")
        result = await synthesize_final_report(verified_breakdown, initial_context)
        print(f"✅ Final report generated with score: {result.score}")
        return result
        
    except Exception as e:
        print(f"❌ Critical error in fact-checking engine: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fact-checking engine error: {str(e)}")

# Engine Helper Functions
async def synthesize_final_report(breakdown: List[ClaimAnalysis], context: str) -> AnalysisResponse:
    """Generate final analysis report using Gemini 2.5 Flash"""
    
    breakdown_text = "\n".join([
        f"Claim: {item.claim}\nVerdict: {item.verdict}\nExplanation: {item.explanation}\n"
        for item in breakdown
    ])
    
    # Use Gemini 2.5 Flash for final synthesis
    final_prompt = f"""
    Analyze the following fact-checking results and provide a comprehensive final assessment:
    
    Claims Analysis:
    {breakdown_text}
    
    Original Context: {context}
    
    Please respond with a JSON object:
    {{
        "overall_verdict": "True|Mostly True|Mixed|Mostly False|False|Insufficient Information",
        "credibility_score": 0-100,
        "summary": "comprehensive summary of findings",
        "key_findings": [
            "finding 1",
            "finding 2"
        ],
        "reliability_indicators": "factors affecting overall reliability",
        "recommendation": "brief recommendation for readers"
    }}
    
    Scoring Guidelines:
    - 85-100: True (overwhelming evidence supports claims)
    - 70-84: Mostly True (majority of claims supported)
    - 50-69: Mixed (conflicting evidence or partial accuracy)
    - 25-49: Mostly False (majority of claims contradicted)
    - 0-24: False (overwhelming evidence contradicts claims)
    """
    
    try:
        response = await query_gemini_text(final_prompt, temperature=0.2)
        
        # Parse Gemini response
        try:
            import json
            report_data = json.loads(response)
            
            overall_verdict = report_data.get("overall_verdict", "Mixed")
            score = int(report_data.get("credibility_score", 50))
            summary = report_data.get("summary", "Analysis completed")
            key_findings = report_data.get("key_findings", [])
            reliability = report_data.get("reliability_indicators", "")
            recommendation = report_data.get("recommendation", "")
            
            # Enhance summary with findings
            enhanced_summary = summary
            if key_findings:
                enhanced_summary += f" Key findings: {'; '.join(key_findings[:2])}"
            if recommendation:
                enhanced_summary += f" {recommendation}"
                
        except json.JSONDecodeError:
            print("⚠️ JSON parsing failed for final report, using fallback analysis")
            
            # Fallback: Calculate score based on breakdown
            supported_count = sum(1 for item in breakdown if item.verdict == "Supported")
            contradicted_count = sum(1 for item in breakdown if item.verdict == "Contradicted")
            insufficient_count = sum(1 for item in breakdown if item.verdict == "InsufficientInfo")
            total_claims = len(breakdown)
            
            if total_claims == 0:
                score = 0
                overall_verdict = "Insufficient Information"
                enhanced_summary = "No factual claims could be identified in the provided content."
            else:
                supported_ratio = supported_count / total_claims
                contradicted_ratio = contradicted_count / total_claims
                
                if contradicted_ratio >= 0.8:
                    score = 15
                    overall_verdict = "False"
                elif contradicted_ratio >= 0.6:
                    score = 35
                    overall_verdict = "Mostly False"
                elif supported_ratio >= 0.8:
                    score = 85
                    overall_verdict = "True"
                elif supported_ratio >= 0.6:
                    score = 72
                    overall_verdict = "Mostly True"
                else:
                    score = 50
                    overall_verdict = "Mixed"
                
                enhanced_summary = f"Analysis of {total_claims} claims: {supported_count} supported, {contradicted_count} contradicted, {insufficient_count} inconclusive. {clean_json_response(response)[:200]}..."
    
    except Exception as e:
        print(f"⚠️ Error in final synthesis: {str(e)}")
        
        # Emergency fallback calculation
        supported_count = sum(1 for item in breakdown if item.verdict == "Supported")
        contradicted_count = sum(1 for item in breakdown if item.verdict == "Contradicted")
        insufficient_count = sum(1 for item in breakdown if item.verdict == "InsufficientInfo")
        total_claims = len(breakdown)
        
        if total_claims == 0:
            score = 50
            overall_verdict = "Insufficient Information"
            enhanced_summary = "We couldn't identify specific factual claims to verify in this content. This might be due to the content being opinion-based, too general, or requiring more context. Try providing more specific factual statements for better analysis."
        else:
            supported_ratio = supported_count / total_claims
            contradicted_ratio = contradicted_count / total_claims
            
            if contradicted_ratio > supported_ratio:
                score = 30
                overall_verdict = "Mostly False"
                enhanced_summary = f"Our analysis found issues with {contradicted_count} out of {total_claims} claims. While some information might be accurate, significant portions appear to contradict established facts."
            elif supported_ratio > contradicted_ratio:
                score = 70
                overall_verdict = "Mostly True"
                enhanced_summary = f"Most claims ({supported_count} out of {total_claims}) appear to be supported by available evidence. However, some aspects require further verification."
            else:
                score = 50
                overall_verdict = "Mixed"
                enhanced_summary = f"The content contains a mix of accurate and questionable information. Out of {total_claims} claims analyzed, {supported_count} were supported and {contradicted_count} were contradicted."
            
            # Add guidance for insufficient info cases
            if insufficient_count > 0:
                enhanced_summary += f" Note: {insufficient_count} claims could not be verified due to insufficient reliable information available."
    
    return AnalysisResponse(
        score=score,
        overallVerdict=overall_verdict,
        summary=enhanced_summary,
        breakdown=breakdown,
        context=context
    )

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
