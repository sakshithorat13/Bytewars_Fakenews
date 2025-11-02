from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import uvicorn
import requests
import base64
import io
from bs4 import BeautifulSoup
import google.generativeai as genai
from PIL import Image
import json
from groq import Groq
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini with environment variable
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Configure API clients with environment variables
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
google_search = build("customsearch", "v1", developerKey=os.getenv("GOOGLE_SEARCH_API_KEY"))

# Pydantic Data Models
class AnalysisRequest(BaseModel):
    inputType: Literal["text", "url", "image"] = Field(alias="type")
    data: str

class ClaimAnalysis(BaseModel):
    claim: str
    verdict: Literal["Contradicted", "Supported", "Insufficient Info"]
    explanation: str

class AnalysisResponse(BaseModel):
    score: int
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
async def analyze_content(request: AnalysisRequest):
    """Main endpoint to analyze content for fact-checking"""
    print("--- 🚀 NEW REQUEST RECEIVED ---")
    print(f"Input Type: {request.inputType}")
    print(f"Data Snippet: {request.data[:100]}")

    extracted_text = ""
    context = ""

    try:
        if request.inputType == "text":
            print("Processing as TEXT...")
            extracted_text = request.data
            context = "Input was a raw text message."
        
        elif request.inputType == "url":
            print("Processing as URL...")
            extracted_text, context = await process_url_input(request.data)
        
        elif request.inputType == "image":
            print("Processing as IMAGE...")
            extracted_text = await process_image_input(request.data)

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
    """Process URL input to extract main article text"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try to find main content areas
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
        
        cleaned_text = ' '.join(text.split())
        context = f"Source URL: {url}"
        
        return cleaned_text, context
        
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")

async def process_image_input(data: str) -> str:
    """Process base64 image input to extract text using Gemini Vision"""
    try:
        image_data = base64.b64decode(data)
        image = Image.open(io.BytesIO(image_data))
        
        model = genai.GenerativeModel('gemini-pro-vision')
        prompt = "Extract all text from this image and describe what you see. Separate the extracted text and description clearly."
        
        response = model.generate_content([prompt, image])
        return response.text
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

# Core Fact-Checking Engine
async def run_fact_checking_engine(text_to_analyze: str, initial_context: str) -> AnalysisResponse:
    """Main multi-step fact-checking logic"""
    
    print("🔍 STARTING FACT-CHECKING ENGINE...")
    print(f"Text to analyze: {text_to_analyze[:100]}...")
    
    # 1. Extract claims using Groq
    print("📝 Step 1: Extracting claims using Groq...")
    system_prompt = "You are a claim extraction expert. Extract all factual claims from the given text and return them as a JSON list of strings. Only return the JSON, nothing else."
    user_prompt = f"Extract claims from this text: {text_to_analyze}"
    
    try:
        claims_response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        print(f"✅ Groq response: {claims_response.choices[0].message.content}")
        
        try:
            claims = json.loads(claims_response.choices[0].message.content)
            print(f"✅ Claims extracted: {claims}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            claims = [text_to_analyze]
            
    except Exception as e:
        print(f"❌ Error calling Groq: {e}")
        claims = [text_to_analyze]
    
    # 2. Process each claim
    print(f"🔍 Step 2: Processing {len(claims)} claims...")
    verified_breakdown = []
    
    for i, claim in enumerate(claims):
        print(f"🔍 Processing claim {i+1}/{len(claims)}: {claim[:50]}...")
        
        # Generate search queries
        try:
            query_prompt = f"Generate 3 specific search queries to verify this claim: {claim}. Return as JSON array of strings."
            query_response = groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "user", "content": query_prompt}]
            )
            
            try:
                queries = json.loads(query_response.choices[0].message.content)
            except json.JSONDecodeError:
                queries = [claim]
        except Exception as e:
            print(f"Error generating queries: {e}")
            queries = [claim]
        
        # Execute Google search
        evidence = await execute_google_search(queries)
        
        # Verify claim with evidence
        verify_prompt = f"""
        Act as a fact verifier. Analyze this claim against the evidence and return a JSON object with:
        {{"claim": "the claim", "verdict": "Contradicted/Supported/Insufficient Info", "explanation": "detailed explanation"}}
        
        Claim: {claim}
        Evidence: {evidence}
        """
        
        try:
            verify_response = groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "user", "content": verify_prompt}]
            )
            
            try:
                claim_analysis = json.loads(verify_response.choices[0].message.content)
                verified_breakdown.append(ClaimAnalysis(**claim_analysis))
            except (json.JSONDecodeError, Exception) as e:
                verified_breakdown.append(ClaimAnalysis(
                    claim=claim,
                    verdict="Insufficient Info",
                    explanation="Unable to verify due to processing error"
                ))
        except Exception as e:
            verified_breakdown.append(ClaimAnalysis(
                claim=claim,
                verdict="Insufficient Info",
                explanation=f"Unable to verify due to API error: {str(e)}"
            ))
    
    # 3. Synthesize final report
    print("📊 Step 3: Synthesizing final report...")
    result = await synthesize_final_report(verified_breakdown, initial_context)
    print(f"✅ Final report generated with score: {result.score}")
    return result

# Engine Helper Functions
async def execute_google_search(queries: List[str]) -> str:
    """Execute Google searches and compile evidence"""
    evidence_parts = []
    
    for query in queries[:3]:
        try:
            result = google_search.cse().list(
                q=query,
                cx=os.getenv("GOOGLE_CSE_ID"),
                num=3
            ).execute()
            
            for item in result.get('items', []):
                snippet = item.get('snippet', '')
                if snippet:
                    evidence_parts.append(snippet)
                    
        except Exception as e:
            print(f"❌ Search error: {e}")
            continue
    
    return " ".join(evidence_parts) if evidence_parts else "No evidence found"

async def synthesize_final_report(breakdown: List[ClaimAnalysis], context: str) -> AnalysisResponse:
    """Generate final analysis report using Gemini"""
    
    breakdown_text = "\n".join([
        f"Claim: {item.claim}\nVerdict: {item.verdict}\nExplanation: {item.explanation}\n"
        for item in breakdown
    ])
    
    prompt = f"""
    Act as a fact-checking analyst. Based on the individual claim analyses below, provide a comprehensive final report.
    Return a JSON object with this exact structure:
    {{
        "score": integer from 0-100 (credibility score),
        "summary": "overall assessment string",
        "context": "additional context or null"
    }}
    
    Context: {context}
    
    Individual Claim Analyses:
    {breakdown_text}
    
    Provide only the JSON object for score, summary, and context (breakdown will be added separately).
    """
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        try:
            final_data = json.loads(response.text)
            return AnalysisResponse(
                score=final_data.get("score", 50),
                summary=final_data.get("summary", "Analysis completed"),
                breakdown=breakdown,
                context=final_data.get("context", context)
            )
        except json.JSONDecodeError:
            return AnalysisResponse(
                score=50,
                summary="Analysis completed with limited confidence",
                breakdown=breakdown,
                context=context
            )
    except Exception as e:
        print(f"❌ Error calling Gemini: {e}")
        return AnalysisResponse(
            score=50,
            summary=f"Analysis completed with errors: {str(e)}",
            breakdown=breakdown,
            context=context
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
