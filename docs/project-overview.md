# Project Overview: Intelligent Content Detection in Photos

**Organization:** CompanyCam
**Project ID:** ad0w8tJrc0PZKTA34A2Y_1762020692703

## What We're Building

An AI-powered photo analysis system that automatically detects and tags content in contractor photos. The system identifies roof damage, verifies material deliveries, and estimates volumes of loose materials—turning raw images into actionable, structured data.

## Core Capabilities

### P0 (Must-Have)
- **Damage Detection**: Automatically identify hail damage, wind/storm damage, and missing shingles on roofs with bounding boxes and severity tags
- **Material Verification**: Detect and count delivered materials (shingles, plywood), verify quantities, and alert on discrepancies

### P1 (Should-Have)
- **Volume Estimation**: Estimate cubic yardage of loose materials (gravel, mulch) using depth estimation
- **Real-time Processing**: Sub-500ms detection at photo capture with auto-tagging

### P2 (Nice-to-Have)
- **AI-Native Features**: Pre-fill insurance claims and job reports, build feedback loops for model improvement

## Technical Approach

**Architecture**: Hybrid edge/cloud processing
- Edge: Lightweight models for instant feedback
- Cloud: Complex AI inference for detailed analysis

**Tech Stack**:
- Backend: Python FastAPI microservices, PostgreSQL, Redis, S3
- AI/ML: PyTorch/TensorFlow (YOLOv8, U-Net, depth estimation models)
- Infrastructure: AWS (EKS, SageMaker, API Gateway)
- Frontend: React Native (mobile), React (web)

**Detection Engines**:
1. Damage Detection Engine (object detection + segmentation)
2. Material Detection Engine (object detection + counting + OCR)
3. Volume Estimation Engine (depth estimation + scale reference)

## Success Metrics

- **Speed**: 90% of photos processed in <500ms
- **Accuracy**: High precision/recall for damage detection and material counts
- **Adoption**: Increased usage in insurance reports, delivery verification, and estimation workflows

## Implementation Approach

The project follows BMAD methodology with three agents:
- **Scrum Master**: Breaks down epics into implementable stories
- **Dev**: Implements features according to architecture
- **QA**: Validates implementations against acceptance criteria

Stories progress through: Draft → Ready for Development → Ready for Review → Done (or In Progress for fixes)

## Key Documents

- **PRD**: `docs/prd.md` - Product requirements and user stories
- **Architecture**: `docs/architecture.md` - Technical architecture and design decisions
- **Orchestration**: `docs/orchestration-flow.md` - Development progress tracking
