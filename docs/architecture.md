# Architecture Document: Intelligent Content Detection in Photos

**Organization:** CompanyCam
**Project ID:** ad0w8tJrc0PZKTA34A2Y_1762020692703
**Version:** 1.0
**Last Updated:** 2025-11-17

---

## 1. Executive Summary

This document outlines the technical architecture for the Intelligent Content Detection in Photos feature. The system leverages AI/ML capabilities to automatically detect, classify, and tag content in contractor photos, focusing on roof damage identification, material delivery confirmation, and loose material sizing.

The architecture follows a hybrid approach combining edge processing for real-time feedback and cloud processing for complex AI inference, ensuring both performance (<500ms processing time) and accuracy.

---

## 2. Architecture Principles

### 2.1 Core Principles

- **Performance First**: Prioritize low-latency processing (<500ms) through intelligent caching and hybrid processing
- **Scalability**: Design for horizontal scaling to handle increased photo volumes
- **Privacy & Security**: Ensure data protection and compliance with industry standards
- **Modularity**: Enable independent development and deployment of detection capabilities
- **Extensibility**: Support future detection types and AI model improvements
- **Cost Efficiency**: Optimize cloud resource usage through intelligent routing and caching

### 2.2 Design Patterns

- **Microservices Architecture**: Separate services for different detection types
- **Event-Driven Processing**: Asynchronous photo processing pipeline
- **CQRS Pattern**: Separate read/write operations for metadata storage
- **Circuit Breaker**: Graceful degradation when AI services are unavailable
- **Caching Strategy**: Multi-level caching for inference results and metadata

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Mobile/Web Client                         │
│  (Photo Capture, UI Display, User Confirmation)                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTPS/REST
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                      API Gateway Layer                           │
│  (Authentication, Rate Limiting, Routing)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
        ┌────────┴─────────┬──────────────────┐
        │                  │                  │
┌───────▼────────┐ ┌──────▼──────┐ ┌────────▼─────────┐
│  Photo Upload  │ │  Detection  │ │   Metadata       │
│   Service      │ │   Service   │ │   Service        │
└───────┬────────┘ └──────┬──────┘ └────────┬─────────┘
        │                  │                  │
        │         ┌────────▼────────┐         │
        │         │  AI Orchestrator│         │
        │         └────────┬────────┘         │
        │                  │                  │
        │         ┌────────┴────────┐         │
        │         │                 │         │
        │   ┌─────▼──────┐  ┌──────▼──────┐  │
        │   │  Damage    │  │  Material   │  │
        │   │  Detection │  │  Detection  │  │
        │   │  Engine    │  │  Engine     │  │
        │   └─────┬──────┘  └──────┬──────┘  │
        │         │                 │         │
┌───────▼─────────▼─────────────────▼─────────▼────────┐
│                   Data Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐            │
│  │  Object  │  │  Photo   │  │  Cache  │            │
│  │ Storage  │  │Metadata  │  │  (Redis)│            │
│  │  (S3)    │  │   (DB)   │  │         │            │
│  └──────────┘  └──────────┘  └─────────┘            │
└───────────────────────────────────────────────────────┘
```

---

## 4. Component Architecture

### 4.1 Client Layer

**Responsibilities:**
- Photo capture and upload
- Display detection results (bounding boxes, tags)
- User confirmation and feedback collection
- Offline-first capabilities for photo capture

**Technology Stack:**
- React Native (Mobile) / React (Web)
- Local storage for offline queuing
- WebSocket for real-time updates

### 4.2 API Gateway

**Responsibilities:**
- Request routing and load balancing
- Authentication and authorization (JWT)
- Rate limiting and throttling
- Request/response transformation
- API versioning

**Technology Stack:**
- AWS API Gateway / Kong / NGINX
- JWT token validation
- OpenAPI/Swagger documentation

### 4.3 Photo Upload Service

**Responsibilities:**
- Receive and validate photo uploads
- Generate pre-signed URLs for direct S3 upload
- Trigger detection pipeline
- Handle photo metadata extraction (EXIF)

**Technology Stack:**
- Node.js / Python FastAPI
- AWS S3 for object storage
- Message queue (SQS/RabbitMQ) for pipeline triggering

**API Endpoints:**
```
POST   /api/v1/photos/upload-url     - Generate upload URL
POST   /api/v1/photos/:id/process    - Trigger detection
GET    /api/v1/photos/:id/status     - Check processing status
```

### 4.4 Detection Service

**Responsibilities:**
- Coordinate detection requests
- Route to appropriate detection engines
- Aggregate results from multiple detectors
- Apply business rules and confidence thresholds
- Return structured detection results

**Technology Stack:**
- Python FastAPI / Go
- gRPC for internal service communication
- Redis for result caching

**API Endpoints:**
```
POST   /api/v1/detect                - Trigger detection
GET    /api/v1/detect/:id/results    - Get detection results
POST   /api/v1/detect/:id/feedback   - Submit user feedback
```

### 4.5 AI Orchestrator

**Responsibilities:**
- Load balancing across AI inference endpoints
- Model version management
- A/B testing for model improvements
- Fallback handling when models are unavailable
- Performance monitoring and logging

**Technology Stack:**
- Python
- Model registry (MLflow / AWS SageMaker)
- Kubernetes for container orchestration

### 4.6 Detection Engines

#### 4.6.1 Damage Detection Engine (P0)

**Capabilities:**
- Detect hail impact damage
- Identify wind/storm damage
- Detect missing shingles
- Classify damage severity
- Generate bounding boxes/segmentation masks

**Models:**
- Object Detection: YOLOv8 / Faster R-CNN
- Semantic Segmentation: U-Net / DeepLabv3
- Classification: ResNet50 / EfficientNet

**Input:** Photo URL, metadata
**Output:**
```json
{
  "detections": [
    {
      "type": "hail_damage",
      "confidence": 0.92,
      "severity": "moderate",
      "bounding_box": {"x": 100, "y": 150, "w": 200, "h": 180},
      "segmentation_mask": "s3://bucket/masks/photo123_damage1.png"
    }
  ],
  "tags": ["roof_damage", "hail_impact", "insurance_claim"],
  "processing_time_ms": 450
}
```

#### 4.6.2 Material Detection Engine (P0)

**Capabilities:**
- Detect shingles, plywood, and other materials
- Count identifiable units
- Identify brand/type when visible
- Compare against expected quantities

**Models:**
- Object Detection: YOLOv8
- Object Counting: Density estimation CNN
- OCR: Tesseract / Cloud Vision API (for brand detection)

**Input:** Photo URL, expected_quantity (optional)
**Output:**
```json
{
  "materials": [
    {
      "type": "shingles",
      "brand": "CertainTeed",
      "count": 35,
      "confidence": 0.88,
      "unit": "bundles",
      "alert": null
    }
  ],
  "tags": ["delivery_confirmation", "shingles"],
  "processing_time_ms": 380
}
```

#### 4.6.3 Volume Estimation Engine (P1)

**Capabilities:**
- Detect loose materials (gravel, mulch, sand)
- Estimate volume in cubic yards
- Use depth estimation and scale references
- Prompt for user confirmation

**Models:**
- Depth Estimation: MiDaS / DPT
- Volume Calculation: Custom algorithm using depth + area
- Object Detection: YOLOv8 (for scale references)

**Input:** Photo URL, reference_object (optional)
**Output:**
```json
{
  "material": "gravel",
  "estimated_volume": 2.5,
  "unit": "cubic_yards",
  "confidence": 0.75,
  "requires_confirmation": true,
  "depth_map": "s3://bucket/depth/photo123.png",
  "processing_time_ms": 520
}
```

### 4.7 Metadata Service

**Responsibilities:**
- Store and retrieve photo metadata
- Manage detection results and tags
- Handle user confirmations and corrections
- Provide search and filtering capabilities
- Support report generation

**Technology Stack:**
- PostgreSQL / MongoDB for metadata storage
- Elasticsearch for full-text search
- Redis for caching

**Data Model:**
```sql
photos:
  - id (UUID)
  - user_id (UUID)
  - project_id (UUID)
  - s3_url (TEXT)
  - uploaded_at (TIMESTAMP)
  - exif_data (JSONB)

detections:
  - id (UUID)
  - photo_id (UUID)
  - detection_type (ENUM)
  - model_version (TEXT)
  - results (JSONB)
  - confidence (FLOAT)
  - created_at (TIMESTAMP)
  - user_confirmed (BOOLEAN)
  - user_feedback (JSONB)

tags:
  - id (UUID)
  - photo_id (UUID)
  - tag (TEXT)
  - source (ENUM: ai, user)
  - confidence (FLOAT)
```

---

## 5. Data Flow

### 5.1 Photo Upload & Detection Flow

```
1. Client captures photo
   ↓
2. Client requests upload URL from Photo Upload Service
   ↓
3. Photo Upload Service generates pre-signed S3 URL
   ↓
4. Client uploads photo directly to S3
   ↓
5. Client triggers detection via Detection Service
   ↓
6. Detection Service publishes message to processing queue
   ↓
7. AI Orchestrator picks up message and routes to engines
   ↓
8. Detection Engines process photo in parallel:
   - Damage Detection Engine
   - Material Detection Engine
   - Volume Estimation Engine (if applicable)
   ↓
9. Results aggregated by AI Orchestrator
   ↓
10. Detection Service stores results in Metadata Service
   ↓
11. Detection Service caches results in Redis
   ↓
12. Client polls/receives results via WebSocket
   ↓
13. Client displays detections with bounding boxes/tags
   ↓
14. User confirms or corrects detections
   ↓
15. Feedback stored in Metadata Service for model improvement
```

### 5.2 Real-Time Detection Flow (P1)

```
1. Client captures photo
   ↓
2. Lightweight on-device model performs initial detection
   ↓
3. Client displays preliminary results immediately
   ↓
4. Photo uploaded to cloud in background
   ↓
5. Cloud models perform detailed detection
   ↓
6. Results streamed back via WebSocket
   ↓
7. Client UI updates with refined detections
```

---

## 6. Technology Stack

### 6.1 Backend Services

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API Gateway | AWS API Gateway / Kong | Managed service, built-in auth, scaling |
| Services | Python FastAPI / Node.js | High performance, async support, ML ecosystem |
| Message Queue | AWS SQS / RabbitMQ | Reliable async processing, decoupling |
| Cache | Redis | Fast in-memory storage, pub/sub support |
| Database | PostgreSQL | ACID compliance, JSONB support |
| Search | Elasticsearch | Full-text search, analytics |
| Object Storage | AWS S3 | Scalable, cost-effective, durability |

### 6.2 AI/ML Infrastructure

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Training | PyTorch / TensorFlow | Industry standard, extensive ecosystem |
| Inference | TorchServe / TensorFlow Serving | Production-ready, model versioning |
| Model Registry | MLflow / AWS SageMaker | Version control, experiment tracking |
| Orchestration | Kubernetes / AWS ECS | Container orchestration, auto-scaling |
| GPUs | AWS EC2 P3/P4 instances | High-performance inference |

### 6.3 Client

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Mobile | React Native | Cross-platform, native performance |
| Web | React | Component reuse, ecosystem |
| State Management | Redux / Zustand | Predictable state, debugging |
| Offline Storage | AsyncStorage / IndexedDB | Offline-first capabilities |

### 6.4 DevOps & Monitoring

| Component | Technology | Rationale |
|-----------|------------|-----------|
| CI/CD | GitHub Actions / GitLab CI | Automation, integration |
| Container Registry | AWS ECR / Docker Hub | Image management |
| Monitoring | Prometheus + Grafana | Metrics, visualization |
| Logging | ELK Stack / CloudWatch | Centralized logging, search |
| Tracing | Jaeger / AWS X-Ray | Distributed tracing |
| Alerts | PagerDuty / OpsGenie | Incident management |

---

## 7. API Design

### 7.1 REST API Conventions

- **Base URL:** `https://api.companycam.com/v1`
- **Authentication:** JWT Bearer tokens
- **Versioning:** URL path versioning (`/v1`, `/v2`)
- **Response Format:** JSON
- **Error Format:** RFC 7807 Problem Details

### 7.2 Core Endpoints

#### Photo Management

```
POST   /photos/upload-url
GET    /photos/:id
DELETE /photos/:id
PATCH  /photos/:id
GET    /photos?project_id=:id&tags=:tags
```

#### Detection

```
POST   /photos/:id/detect
GET    /photos/:id/detections
GET    /detections/:id
POST   /detections/:id/feedback
```

#### Tags

```
GET    /photos/:id/tags
POST   /photos/:id/tags
DELETE /photos/:id/tags/:tagId
```

#### Reports

```
GET    /projects/:id/reports/damage
GET    /projects/:id/reports/materials
POST   /reports/insurance-claim
```

### 7.3 WebSocket Events

```
ws://api.companycam.com/v1/ws

Events:
- detection.started
- detection.progress
- detection.completed
- detection.failed
```

### 7.4 Example Request/Response

**Request:**
```http
POST /v1/photos/abc123/detect
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "detection_types": ["damage", "materials"],
  "priority": "high",
  "notify_webhook": "https://app.companycam.com/webhooks/detection"
}
```

**Response:**
```json
{
  "detection_id": "det_xyz789",
  "status": "processing",
  "estimated_completion_ms": 500,
  "links": {
    "self": "/v1/detections/det_xyz789",
    "results": "/v1/detections/det_xyz789/results",
    "photo": "/v1/photos/abc123"
  }
}
```

---

## 8. Security & Privacy

### 8.1 Authentication & Authorization

- **User Authentication:** OAuth 2.0 / JWT tokens
- **Service-to-Service:** mTLS certificates
- **API Keys:** For webhook callbacks
- **RBAC:** Role-based access control for photos and projects

### 8.2 Data Protection

- **Encryption at Rest:** AES-256 for S3, database encryption
- **Encryption in Transit:** TLS 1.3 for all API communication
- **PII Handling:** No storage of personal information in photos
- **Data Retention:** Configurable retention policies, GDPR compliance

### 8.3 Compliance

- **GDPR:** Data portability, right to erasure
- **SOC 2 Type II:** Security controls and auditing
- **Privacy:** Photo data isolated per organization

### 8.4 Security Best Practices

- Input validation and sanitization
- Rate limiting and DDoS protection
- SQL injection prevention (parameterized queries)
- XSS prevention
- CORS configuration
- Security headers (CSP, HSTS)
- Regular security audits and penetration testing

---

## 9. Performance & Scalability

### 9.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Photo Upload | < 2s for 10MB photo | P95 latency |
| Detection Processing | < 500ms | P90 latency |
| API Response Time | < 200ms | P95 latency |
| Concurrent Users | 10,000+ | Load testing |
| Photos/day | 1M+ | Throughput |

### 9.2 Scaling Strategy

**Horizontal Scaling:**
- Stateless services for easy replication
- Load balancing across service instances
- Auto-scaling based on CPU/memory/queue depth

**Vertical Scaling:**
- GPU instances for AI inference
- Database read replicas
- Cache scaling (Redis cluster)

**Geographic Distribution:**
- Multi-region deployment for low latency
- CDN for static assets and photo thumbnails
- Edge caching for frequently accessed data

### 9.3 Optimization Techniques

**Caching Strategy:**
- L1: In-memory cache (service-level)
- L2: Redis (distributed cache)
- L3: CDN (edge cache)
- Cache invalidation on user feedback

**Database Optimization:**
- Indexed queries on photo_id, user_id, project_id
- Partitioning by date for large tables
- Connection pooling
- Read replicas for analytics queries

**AI Inference Optimization:**
- Model quantization (INT8) for faster inference
- Batch processing for similar photos
- GPU instance optimization
- Model caching and warmup

**Network Optimization:**
- Response compression (gzip/brotli)
- Pagination for large result sets
- GraphQL for flexible queries (future)

### 9.4 Queue Management

- Separate queues for priority levels (high/normal/low)
- Dead letter queues for failed processing
- Retry logic with exponential backoff
- Queue depth monitoring and auto-scaling

---

## 10. Deployment Architecture

### 10.1 Environment Strategy

| Environment | Purpose | Configuration |
|-------------|---------|---------------|
| Development | Local development | Docker Compose, mock AI services |
| Staging | Integration testing | Smaller instances, production-like |
| Production | Live service | Multi-AZ, auto-scaling, monitoring |

### 10.2 Infrastructure as Code

- **Terraform:** Infrastructure provisioning
- **Kubernetes:** Container orchestration
- **Helm Charts:** Application deployment
- **GitOps:** Automated deployments via Git

### 10.3 CI/CD Pipeline

```
Code Commit → GitHub Actions
   ↓
Linting & Unit Tests
   ↓
Build Docker Images
   ↓
Push to Container Registry
   ↓
Deploy to Staging
   ↓
Integration Tests
   ↓
Manual Approval
   ↓
Deploy to Production (Blue/Green)
   ↓
Health Checks
   ↓
Switch Traffic
```

### 10.4 Deployment Diagram (AWS)

```
┌─────────────────────────────────────────────────────────────┐
│                    Route 53 (DNS)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  CloudFront (CDN)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Application Load Balancer                      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
┌────────▼────────┐            ┌────────▼────────┐
│   EKS Cluster   │            │   EKS Cluster   │
│     (AZ-1)      │            │     (AZ-2)      │
│                 │            │                 │
│ - API Services  │            │ - API Services  │
│ - Detection Svc │            │ - Detection Svc │
│ - AI Engines    │            │ - AI Engines    │
└────────┬────────┘            └────────┬────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
┌────────▼────────┐            ┌────────▼────────┐
│   RDS Primary   │◄──────────►│  RDS Replica    │
│  (PostgreSQL)   │            │  (Read-only)    │
└─────────────────┘            └─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  S3 (Photo Storage)                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│            ElastiCache (Redis Cluster)                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                SQS (Processing Queue)                       │
└─────────────────────────────────────────────────────────────┘
```

### 10.5 Disaster Recovery

- **RTO (Recovery Time Objective):** < 1 hour
- **RPO (Recovery Point Objective):** < 5 minutes
- **Backup Strategy:**
  - Database: Automated daily backups, point-in-time recovery
  - S3: Versioning enabled, cross-region replication
  - Configuration: Version controlled in Git
- **Failover:** Multi-AZ deployment, automated health checks

---

## 11. Monitoring & Observability

### 11.1 Metrics to Track

**Application Metrics:**
- Request rate, latency, error rate (RED metrics)
- Detection accuracy, confidence scores
- Processing time per detection type
- Cache hit rates
- Queue depth and processing lag

**Infrastructure Metrics:**
- CPU, memory, disk, network utilization
- Database connections, query performance
- GPU utilization for AI inference
- S3 request rates and data transfer

**Business Metrics:**
- Photos uploaded per day
- Detection types requested
- User confirmations vs corrections
- Insurance reports generated
- Material verification completions

### 11.2 Logging Strategy

- **Structured Logging:** JSON format with correlation IDs
- **Log Levels:** DEBUG, INFO, WARN, ERROR, CRITICAL
- **Retention:** 30 days in hot storage, 1 year in cold storage
- **Sensitive Data:** Redact PII and credentials

### 11.3 Alerting

**Critical Alerts:**
- Service downtime (>5xx error rate threshold)
- Database connection failures
- AI inference failures (>10% error rate)
- Processing queue backlog (>1000 messages)

**Warning Alerts:**
- High latency (P95 > 1s)
- Low cache hit rate (<70%)
- Elevated error rate (>1%)

### 11.4 Tracing

- Distributed tracing across microservices
- Trace all requests with unique correlation IDs
- Visualize service dependencies and bottlenecks

---

## 12. Model Management & MLOps

### 12.1 Model Lifecycle

```
Data Collection
   ↓
Data Labeling & Annotation
   ↓
Model Training
   ↓
Model Evaluation
   ↓
Model Registration (MLflow)
   ↓
Staging Deployment
   ↓
A/B Testing
   ↓
Production Deployment
   ↓
Monitoring & Feedback
   ↓
Model Retraining (loop back)
```

### 12.2 Model Versioning

- Semantic versioning for models (v1.0.0, v1.1.0)
- Track model lineage (dataset, hyperparameters, training code)
- Rollback capability to previous versions
- Canary deployments for new models

### 12.3 Feedback Loop

- Collect user confirmations and corrections
- Store feedback in training dataset
- Periodic model retraining (monthly or quarterly)
- Track model drift and performance degradation

### 12.4 Experimentation

- A/B testing framework for model comparison
- Feature flags for gradual rollout
- Metrics tracking per model version
- Statistical significance testing

---

## 13. Testing Strategy

### 13.1 Testing Pyramid

**Unit Tests (70%):**
- Service logic
- Data validation
- Utility functions
- Coverage target: >80%

**Integration Tests (20%):**
- API endpoint tests
- Database interactions
- Service-to-service communication
- Message queue processing

**End-to-End Tests (10%):**
- Complete user workflows
- Photo upload → detection → results
- Report generation

### 13.2 AI Model Testing

- **Benchmark Datasets:** Curated test sets with ground truth
- **Accuracy Metrics:** Precision, recall, F1-score, mAP
- **Performance Testing:** Inference latency, throughput
- **Regression Testing:** Ensure new models don't degrade
- **Edge Case Testing:** Low-quality photos, unusual angles

### 13.3 Load Testing

- Simulate 10,000+ concurrent users
- Test auto-scaling behavior
- Identify bottlenecks
- Validate SLA targets

---

## 14. Cost Optimization

### 14.1 Cost Drivers

- AI inference compute (GPU instances)
- Photo storage (S3)
- Data transfer
- Database operations
- API Gateway requests

### 14.2 Optimization Strategies

**Compute:**
- Use spot instances for batch processing
- Auto-scale down during low traffic
- Optimize model inference (quantization, pruning)
- Batch similar requests

**Storage:**
- Lifecycle policies (move to S3 Glacier after 90 days)
- Compress photos when possible
- Delete temporary artifacts

**Data Transfer:**
- Use CloudFront for caching
- Regional data processing to minimize cross-region transfer
- Compress responses

**Database:**
- Right-size instances based on usage
- Archive old data
- Optimize queries

---

## 15. Future Considerations

### 15.1 P2 Features

**AI-Native Opportunities:**
- Pre-fill insurance claims with detected damage
- Auto-generate job reports from photos
- Predictive material ordering based on detection history
- Integration with CRM/ERP systems

### 15.2 Advanced Capabilities

**Technical Enhancements:**
- 3D reconstruction from multiple photos
- Video analysis for dynamic damage assessment
- Edge AI for fully offline detection
- Multi-photo stitching and panoramas
- Temporal analysis (damage progression over time)

**Business Enhancements:**
- Industry-specific models (HVAC, plumbing, electrical)
- Custom model training for enterprise customers
- White-label API for third-party integrations
- Marketplace for detection plugins

### 15.3 Scalability Roadmap

- Multi-tenancy architecture for enterprise
- Global expansion (GDPR, data residency)
- Real-time collaboration on photos
- Integration with IoT devices (drones, smart cameras)

---

## 16. Open Questions & Decisions Needed

1. **Model Hosting:** Self-hosted vs. managed (AWS SageMaker, GCP Vertex AI)?
2. **Database Choice:** PostgreSQL vs. MongoDB for metadata?
3. **Real-time vs. Async:** Should all detections be async or offer real-time option?
4. **Pricing Model:** Per-photo, per-detection, subscription-based?
5. **Data Labeling:** Build in-house vs. third-party service (Scale AI, Labelbox)?
6. **Edge Processing:** Which models can run on-device?

---

## 17. References & Resources

- **PRD:** [docs/prd.md](./prd.md)
- **API Documentation:** TBD
- **Model Documentation:** TBD
- **Deployment Runbooks:** TBD
- **Security Policies:** TBD

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Bounding Box | Rectangular region highlighting detected object |
| Confidence Score | Probability (0-1) of detection accuracy |
| Inference | Process of running AI model on new data |
| mAP | Mean Average Precision, detection accuracy metric |
| Segmentation Mask | Pixel-level classification of image regions |
| EXIF | Metadata embedded in photos (location, timestamp) |

---

## Appendix B: Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-17 | Architecture Team | Initial architecture document |

---

**Document Status:** Draft
**Review Status:** Pending Review
**Approval Status:** Pending Approval
