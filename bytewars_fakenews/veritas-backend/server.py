import os
import base64
import io
import requests
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import google.generativeai as genai
from groq import Groq
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Veritas API",
    description="A comprehensive fact-checking API that verifies news articles, claims, and media content using AI and web scraping techniques.",
    version="1.0.0"
)

# Initialize API clients
genai.configure(api_key="AIzaSyDv6AID1KafMPyKjyJj2VT-EjerWPppY4Y")
groq_client = Groq(api_key="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")
google_search = build("customsearch", "v1", developerKey=os.getenv("GOOGLE_API_KEY"))

@app.get("/")
def read_root():
    return {"message": "Veritas Fact-Checking API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "veritas-backend"}
