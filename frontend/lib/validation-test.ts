/**
 * Validation testing utilities
 * Can be used in browser console or test files
 */

import { MessageSchema, ConversationSchema, MessageRoleSchema } from '@/types';

/**
 * Test message validation
 */
export function testMessageValidation() {
  const results: string[] = [];

  // Test valid message
  try {
    const validMessage = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      role: 'user' as const,
      content: 'Hello',
      createdAt: new Date(),
    };
    const result = MessageSchema.parse(validMessage);
    results.push('✅ Valid message passed');
    console.log('Valid message result:', result);
  } catch (error: any) {
    results.push(`❌ Valid message failed: ${error.message}`);
    console.error('Validation error:', error);
  }

  // Test invalid role
  try {
    const invalidMessage = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      role: 'invalid' as any,
      content: 'Hello',
      createdAt: new Date(),
    };
    MessageSchema.parse(invalidMessage);
    results.push('❌ Invalid role should have failed');
  } catch (error: any) {
    results.push(`✅ Invalid role correctly rejected: ${error.message}`);
  }

  // Test empty content
  try {
    const emptyContent = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      role: 'user' as const,
      content: '',
      createdAt: new Date(),
    };
    MessageSchema.parse(emptyContent);
    results.push('❌ Empty content should have failed');
  } catch (error: any) {
    results.push(`✅ Empty content correctly rejected: ${error.message}`);
  }

  // Test invalid UUID
  try {
    const invalidId = {
      id: 'not-a-uuid',
      role: 'user' as const,
      content: 'Hello',
      createdAt: new Date(),
    };
    MessageSchema.parse(invalidId);
    results.push('❌ Invalid UUID should have failed');
  } catch (error: any) {
    results.push(`✅ Invalid UUID correctly rejected: ${error.message}`);
  }

  return results;
}

/**
 * Test conversation validation
 */
export function testConversationValidation() {
  const results: string[] = [];

  try {
    const validConversation = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      createdAt: new Date(),
      updatedAt: new Date(),
      messages: [
        {
          id: '223e4567-e89b-12d3-a456-426614174000',
          role: 'user' as const,
          content: 'Hello',
          createdAt: new Date(),
        },
      ],
    };
    const result = ConversationSchema.parse(validConversation);
    results.push('✅ Valid conversation passed');
    console.log('Valid conversation result:', result);
  } catch (error: any) {
    results.push(`❌ Valid conversation failed: ${error.message}`);
    console.error('Validation error:', error);
  }

  return results;
}

// Expose schemas globally in development for browser console testing
// This must be after function definitions
if (typeof window !== 'undefined') {
  const win = window as any;
  win.__validationSchemas = {
    MessageSchema,
    ConversationSchema,
    MessageRoleSchema,
    testMessageValidation,
    testConversationValidation,
  };
  
  if (process.env.NODE_ENV === 'development') {
    console.log('✅ Validation schemas available at window.__validationSchemas');
    console.log('   Try: window.__validationSchemas.testMessageValidation()');
  }
}
