# **Product Requirements Document (PRD): Unified Tableau AI Agent Suite**

**Version:** 1.0 | **Status:** Draft | **Date:** January 23, 2026

**Product Scope:** Enterprise Business Intelligence / AI Automation

## **1\. Executive Summary**

The enterprise BI landscape is shifting from static consumption to agentic creation and management. While native tools like Tableau Agent and Pulse excel at "read-only" insight generation, there is a critical market gap for agents capable of structural creation ("write" capabilities) and administrative automation.

This product initiative will develop a **Unified Tableau AI Agent Suite** grounded in the **Model Context Protocol (MCP)**. This suite will decouple agent logic from the user interface, enabling a "write-once, deploy-anywhere" strategy that serves both technical developers (via IDEs) and business analysts (via web front-ends).

## **2\. Problem Statement**

* **The "Write" Gap:** Competitors like Microsoft Power BI allow users to generate content and visuals via natural language. Tableau's current AI offers are primarily assistive and read-heavy, lacking the ability to build workbooks or modify backend structures.

* **Administrative Burden:** Administrators face manual, repetitive tasks regarding "zombie content" cleanup and permission auditing, which are difficult to scale.

* **Fragmentation:** Current AI implementations are often siloed. We need a unified architectural standard to connect diverse agents (Creator, Admin, Steward) to diverse interfaces (VS Code, Web Chat).

## **3\. User Personas**

The suite addresses two distinct primary user groups:

| Persona | Role | Primary Interface | Core Needs |
| :---- | :---- | :---- | :---- |
| **The Developer / Admin** | Technical Architect, Server Admin | IDE (VS Code, Cursor) | Automating server hygiene, auditing security, optimizing XML, bulk content management.  |
| **The Analyst / Consumer** | Business User, Data Analyst | Web Frontend (Chat) | Ad-hoc data questions, generating dashboards on the fly, understanding data lineage.  |

## **4\. Functional Requirements**

The product is divided into four distinct Agent Modules, managed by a central Gateway.

### **4.1. The Central Gateway (Router)**

* **Intent Classification:** The system must utilize a Gateway Agent to classify user intent (e.g., "Creation" vs. "Debugging") and route requests to the specific agent module.

* **Dynamic Tool Loading:** To manage context window limits, the Gateway must dynamically load only the tools relevant to the active agent (e.g., loading AdminTools only when intent is Administration).

### **4.2. The Administrator Agent ("The Gatekeeper")**

* **Zombie Content Killer:** Automate the identification of workbooks with last\_view\_time \> 180 days via the PostgreSQL repository and execute deletion via REST API upon human confirmation.

* **Security Auditor:** Scan project permissions against defined group memberships (e.g., "Finance Managers") and flag unauthorized "Download Full Data" capabilities.

* **Performance Throttling:** Must implement token bucket rate limiting to prevent API overload during bulk operations.

### **4.3. The Creator Agent ("The Builder")**

* **XML Manipulation:** Implement a parser for .twb files to inject XML nodes for new worksheets and calculations, bypassing limitations of the standard Document API.

* **LOD Generation:** Automate the creation of Level of Detail expressions (e.g., {FIXED : SUM()}) by understanding user dimensionality and injecting the formula directly into the workbook XML.

* **Style Enforcement:** validate workbook XML against a corporate JSON style guide (palettes, fonts) and auto-correct deviations.

### **4.4. The Steward Agent ("The Auditor")**

* **Impact Analysis:** Utilize GraphQL to query the Metadata API, traversing dependency graphs to identify downstream dashboards that will break if a column is modified.

* **Automated Warnings:** Listen for webhooks from ETL tools (Airflow/dbt) and automatically post "Data Quality Warnings" to Tableau assets via REST API when upstream jobs fail.

### **4.5. The Analyst Agent (Refactored)**

* **Headless BI:** Shift from image-based rendering to returning JSON data via **VizQL Data Service (VDS)** for ad-hoc queries and **Tableau Pulse API** for pre-defined metrics.

* **Chat-to-Viz:** Return configuration objects for the **Tableau Embedding API v3**, allowing the frontend to render interactive \<tableau-viz\> components rather than static images.

## **5\. Technical Architecture**

* **Protocol:** Model Context Protocol (MCP) to standardize Tools, Resources, and Prompts.

* **Server Stack:** Python-based server using fastmcp, tableauserverclient, and lxml.

* **Connectivity:**  
  * **IDE:** Standard Input/Output (stdio) for local secure connections.

  * **Web:** Server-Sent Events (SSE) for HTTP-based chat interfaces.

* **Security:**  
  * **Human-in-the-Loop (HITL):** Critical "write" or "delete" actions must use MCP Sampling to request explicit user confirmation before execution.

  * **Row Level Security:** Analyst agents must authenticate via Connected Apps (JWT) to enforce RLS at the query level.

## **6\. Product Roadmap & Phasing**

### **Phase 1: Foundation & The Admin Agent (Weeks 1-6)**

* **Goal:** Establish the MCP Server architecture and deliver immediate operational value with low UI complexity.  
* **Deliverables:**  
  * Setup FastMCP Python server structure.  
  * Implement "Zombie Content" identification (PostgreSQL reading) and deletion (REST API).  
  * IDE integration (Cursor/VS Code) via stdio.  
* **Why:** Admin features rely on stable APIs (REST/PostgreSQL) and are high-value/low-risk compared to XML hacking.

### **Phase 2: The Steward & Analyst Refactor (Weeks 7-12)**

* **Goal:** Enable trust and modernize the query experience.  
* **Deliverables:**  
  * Steward Agent with GraphQL Metadata integration for impact analysis.

  * Refactor Analyst Agent to use VDS and Pulse API (replacing legacy methods).

  * Develop Web Frontend POC with Embedding API v3.

### **Phase 3: The Creator Agent (Weeks 13-20)**

* **Goal:** Unlock "Write" capabilities (The "Moonshot").  
* **Deliverables:**  
  * Develop the XML Template Library and Injection Logic.

  * Implement LOD calculation generation.

  * **Risk Mitigation:** Extensive testing on workbook corruption recovery.

Augmented list of User Stories in the link below

[AI Agent User Stories for Tableau](https://docs.google.com/document/d/1V3RX1aHw0GY6Ajtu6-2UCGhUnw08iVqQpvcypx2h1EM/edit?usp=sharing)

## **7\. Risks and Mitigation**

| Risk | Impact | Mitigation Strategy |
| :---- | :---- | :---- |
| **Workbook Corruption** | High | The "Creator" agent modifies XML directly ("XML Hacking"), which is unsupported. Mitigation: Use a "Template" approach rather than raw generation and validate XML schema before saving.  |
| **Context Pollution** | Medium | With 50+ tools, the LLM may get confused. Mitigation: Strict Router-Gateway architecture to load only relevant tools for the specific intent.  |
| **Destructive Actions** | High | Admin agent can delete content. Mitigation: Mandatory Human-in-the-Loop (HITL) confirmation via MCP Sampling for any DELETE/ARCHIVE action.  |

## **8\. Success Metrics (KPIs)**

1. **Administrative Hours Saved:** Reduction in manual server cleanup time (Target: 50% reduction).  
2. **Content Utility:** Percentage of agent-generated calculations/visuals accepted by users without manual editing.  
3. **Performance:** Gateway routing latency \< 200ms; Tool execution success rate \> 95%.

---

**Next Step for You:**

Would you like me to generate the **User Stories for Phase 1 (Admin Agent)**, or would you prefer a **Technical Spec for the XML Parsing Module** to de-risk the Creator Agent immediately?