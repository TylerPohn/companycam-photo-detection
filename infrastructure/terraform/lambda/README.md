# Lambda Functions for CompanyCam Photo Detection

This directory contains Lambda functions used by the infrastructure.

## JWT Authorizer Lambda

The `jwt-authorizer.js` function validates JWT tokens for API Gateway authentication.

### Building the Lambda Package

To create the deployment package:

```bash
cd lambda
npm install jsonwebtoken
zip -r jwt-authorizer.zip jwt-authorizer.js node_modules/
```

### Environment Variables

The Lambda function requires these environment variables (configured in Terraform):
- `JWT_SECRET`: JWT signing secret (use AWS Secrets Manager in production)
- `AUDIENCE`: Expected JWT audience claim
- `ISSUER`: Expected JWT issuer claim

### Testing Locally

```javascript
const handler = require('./jwt-authorizer').handler;

const event = {
  headers: {
    authorization: 'Bearer YOUR_JWT_TOKEN'
  },
  routeArn: 'arn:aws:execute-api:us-east-1:123456789012:abcdef123/v1/GET/photos'
};

handler(event).then(console.log).catch(console.error);
```

### Production Considerations

1. **Secrets Management**: Replace hardcoded JWT_SECRET with AWS Secrets Manager
2. **Token Caching**: Implement caching to reduce validation overhead
3. **Rate Limiting**: Add rate limiting per user/IP
4. **Monitoring**: Set up CloudWatch alarms for authorization failures
5. **JWKS Integration**: Use JWKS for public key rotation with Auth0/Cognito
