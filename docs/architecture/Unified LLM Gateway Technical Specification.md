This technical specification outlines the design for a **Unified LLM Gateway**. It acts as a single point of entry for your agents, abstracting the complexities of multiple authentication schemes (Static Keys, JWT OAuth, and Service Accounts) and request formats (OpenAI, Salesforce, and Vertex AI).

## ---

**1\. System Overview**

The Gateway exposes an **OpenAI-compatible interface** to the Agent while managing the following backend integration strategies:

* **Direct Passthrough:** Transparent routing to OpenAI/Anthropic using client-provided keys.  
* **Salesforce Models API:** Integration with Salesforce’s secure Einstein Platform using JWT-based OAuth.  
* **Vertex AI (GCP):** Integration with Google’s Gemini models using Service Account JSON credentials.  
* **Private/Internal:** Secure routing to non-public endpoints via internal network headers.

## ---

**2\. Authentication Strategy Matrix**

| Inbound Auth Type | Backend Provider | Logic Flow |
| :---- | :---- | :---- |
| **User Key** | OpenAI / Anthropic | Proxy adds the key directly to the request header. |
| **Internal Proxy Key** | Salesforce | Exchange Proxy Key for a **JWT**, then exchange JWT for an **OAuth Bearer Token**. |
| **Service Account** | Vertex AI | Load **JSON File** $\\rightarrow$ Sign JWT $\\rightarrow$ Fetch **OAuth2 Access Token**. |

## ---

**3\. Implementation Specification**

### **A. The Core Routing Logic**

The Gateway uses a strategy pattern to determine which "Translator" and "Authenticator" to invoke.

Python

async def unified\_llm\_gateway(request\_body, auth\_header):  
    \# Determine provider context from model name or custom header  
    context \= resolve\_context(request\_body.get("model"))  
      
    \# 1\. AUTHENTICATION PHASE  
    if context.provider \== "vertex":  
        \# Google Service Account Flow  
        token \= await get\_google\_oauth\_token(context.credentials\_path)  
    elif context.provider \== "salesforce":  
        \# SFDC Connected App Flow  
        token \= await get\_salesforce\_jwt\_token(context.client\_id, context.private\_key)  
    else:  
        \# Standard Key Flow  
        token \= auth\_header.replace("Bearer ", "")

    \# 2\. TRANSLATION PHASE  
    target\_url, payload \= transform\_request(request\_body, context)  
      
    \# 3\. DISPATCH PHASE  
    return await dispatch\_request(target\_url, payload, token, context.provider)

### **B. Vertex AI Adapter (JSON Credentials)**

Vertex AI requires converting the messages array into contents and parts.

Python

def transform\_to\_vertex(openai\_payload):  
    vertex\_contents \= \[\]  
    for msg in openai\_payload\["messages"\]:  
        role \= "user" if msg\["role"\] in \["user", "system"\] else "model"  
        vertex\_contents.append({  
            "role": role,  
            "parts": \[{"text": msg\["content"\]}\]  
        })  
      
    return {  
        "contents": vertex\_contents,  
        "generationConfig": {  
            "temperature": openai\_payload.get("temperature", 0.7),  
            "maxOutputTokens": openai\_payload.get("max\_tokens", 1024)  
        }  
    }

### **C. Salesforce Models API Adapter**

This adapter handles the nested parameters requirement and the model-specific URL path.

Python

def transform\_to\_sfdc(openai\_payload):  
    \# Salesforce expects parameters like top\_p and temperature inside a nested object  
    return {  
        "messages": openai\_payload\["messages"\],  
        "parameters": {  
            "temperature": openai\_payload.get("temperature", 1.0),  
            "top\_p": openai\_payload.get("top\_p", 0.95)  
        }  
    }  
\# Salesforce URL: https://api.salesforce.com/einstein/platform/v1/models/{modelName}/chat-generations

## ---

**4\. Key Security & Operational Considerations**

### **I. Token Lifecycle Management**

* **Caching:** Bearer tokens for Salesforce and Vertex AI should be cached (e.g., in Redis) with an expiration 5 minutes shorter than the token TTL to avoid race conditions.  
* **Rotation:** Use a Secret Manager (AWS Secrets Manager or Google Secret Manager) rather than hardcoding JSON files in the proxy environment.

### **II. The Salesforce "Trust" Handshake**

When your agent calls the Salesforce Models API, the proxy must include the x-sfdc-app-context: EinsteinGPT header. This ensures the request is audited through the **Einstein Trust Layer**, which provides PII masking before the data reaches the underlying LLM.

### **III. Request Normalization**

To ensure the Agent is agnostic, the proxy **must** normalize all responses back to the OpenAI choices\[0\].message format:

* **Vertex AI:** Extract from candidates\[0\].content.parts\[0\].text.  
* **Salesforce:** Extract from choices\[0\].message.content.

**Would you like me to generate the full requirements.txt and a Dockerfile to package this gateway into a deployable microservice?**