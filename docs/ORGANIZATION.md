# Documentation Organization

This document explains how the documentation is organized in this project.

## Directory Structure

```
docs/
├── README.md                    # Documentation index
├── prd/                         # Product Requirements Documents
│   └── PRD_ AI Agent Suite for Tableau.md
├── architecture/                # Architecture and design documents
│   ├── ARCHITECTURE.md
│   ├── MULTI_AGENT_ARCHITECTURE.md
│   ├── AGENT_IMPLEMENTATION.md
│   └── Unified LLM Gateway Technical Specification.md
├── deployment/                  # Deployment guides
│   ├── DEPLOYMENT.md
│   ├── MCP_SERVER_DEPLOYMENT.md
│   └── HTTPS_SETUP.md
├── sprints/                     # Sprint summaries
│   ├── SPRINT1_SUMMARY.md
│   ├── SPRINT2_SUMMARY.md
│   ├── SPRINT3_SUMMARY.md
│   └── SPRINT5_SUMMARY.md
├── api/                         # API documentation (future)
└── PLAN.md                      # Project planning document
```

## File Organization Rules

1. **PRD Documents**: All product requirements documents go in `docs/prd/`
2. **Architecture Docs**: System design, architecture, and technical specifications in `docs/architecture/`
3. **Deployment Guides**: All deployment-related documentation in `docs/deployment/`
4. **Sprint Summaries**: Development sprint documentation in `docs/sprints/`
5. **General Docs**: Planning, code review notes, and other general docs in `docs/` root

## Naming Conventions

- Use UPPERCASE for main documents: `ARCHITECTURE.md`, `DEPLOYMENT.md`
- Use descriptive names with spaces or underscores: `PRD_ AI Agent Suite for Tableau.md`
- Sprint summaries: `SPRINT{N}_SUMMARY.md`
- Keep filenames concise but descriptive

## Adding New Documentation

When adding new documentation:

1. Place it in the appropriate subdirectory
2. Update `docs/README.md` to include a link
3. Update this file if creating a new category
4. Follow the naming conventions above

## Migration Notes

The following files were moved during organization:

- `ARCHITECTURE.md` → `docs/architecture/ARCHITECTURE.md`
- `MULTI_AGENT_ARCHITECTURE.md` → `docs/architecture/MULTI_AGENT_ARCHITECTURE.md`
- `AGENT_IMPLEMENTATION.md` → `docs/architecture/AGENT_IMPLEMENTATION.md`
- `DEPLOYMENT.md` → `docs/deployment/DEPLOYMENT.md`
- `MCP_SERVER_DEPLOYMENT.md` → `docs/deployment/MCP_SERVER_DEPLOYMENT.md`
- `PLAN.md` → `docs/PLAN.md`
- `PRD_ AI Agent Suite for Tableau.md` → `docs/prd/PRD_ AI Agent Suite for Tableau.md`
- Sprint summaries moved from `backend/SPRINT*.md` → `docs/sprints/`
