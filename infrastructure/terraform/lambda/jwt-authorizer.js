/**
 * JWT Authorizer Lambda Function for API Gateway
 *
 * This function validates JWT tokens and returns an IAM policy
 * allowing or denying access to API Gateway routes.
 *
 * Environment Variables:
 * - JWT_SECRET: Secret key for JWT validation (use AWS Secrets Manager in production)
 * - AUDIENCE: Expected JWT audience
 * - ISSUER: Expected JWT issuer
 */

const jwt = require('jsonwebtoken');

exports.handler = async (event) => {
  console.log('Authorizer event:', JSON.stringify(event, null, 2));

  try {
    const token = extractToken(event.headers.authorization);

    if (!token) {
      return generatePolicy('user', 'Deny', event.routeArn);
    }

    // Validate JWT token
    const decoded = jwt.verify(token, process.env.JWT_SECRET, {
      audience: process.env.AUDIENCE,
      issuer: process.env.ISSUER,
    });

    console.log('Decoded token:', decoded);

    // Extract user ID from token
    const userId = decoded.sub || decoded.userId;

    // Generate allow policy with context
    return generatePolicy(userId, 'Allow', event.routeArn, {
      userId: userId,
      email: decoded.email || '',
      roles: JSON.stringify(decoded.roles || []),
    });

  } catch (error) {
    console.error('Authorization error:', error.message);
    return generatePolicy('user', 'Deny', event.routeArn);
  }
};

/**
 * Extract JWT token from Authorization header
 */
function extractToken(authHeader) {
  if (!authHeader) {
    return null;
  }

  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') {
    return null;
  }

  return parts[1];
}

/**
 * Generate IAM policy for API Gateway
 */
function generatePolicy(principalId, effect, resource, context = {}) {
  return {
    principalId: principalId,
    policyDocument: {
      Version: '2012-10-17',
      Statement: [
        {
          Action: 'execute-api:Invoke',
          Effect: effect,
          Resource: resource,
        },
      ],
    },
    context: context,
  };
}
