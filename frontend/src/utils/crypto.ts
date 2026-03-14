/**
 * 加密工具函数
 * 使用Web Crypto API实现AES-GCM加密
 */

// 生成加密密钥
export async function generateKey(): Promise<CryptoKey> {
  return await window.crypto.subtle.generateKey(
    {
      name: 'AES-GCM',
      length: 256,
    },
    true,
    ['encrypt', 'decrypt']
  )
}

// 从密码派生密钥
export async function deriveKeyFromPassword(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const encoder = new TextEncoder()
  const passwordBuffer = encoder.encode(password)

  // 使用PBKDF2派生密钥
  const keyMaterial = await window.crypto.subtle.importKey(
    'raw',
    passwordBuffer,
    'PBKDF2',
    false,
    ['deriveBits', 'deriveKey']
  )

  return await window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: salt as unknown as BufferSource,
      iterations: 100000,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt', 'decrypt']
  )
}

// 加密数据
export async function encryptData(data: ArrayBuffer, key: CryptoKey): Promise<{ encrypted: ArrayBuffer; iv: Uint8Array }> {
  // 生成随机初始化向量
  const iv = window.crypto.getRandomValues(new Uint8Array(12))
  
  const encrypted = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv,
    },
    key,
    data
  )
  
  return { encrypted, iv }
}

// 解密数据
export async function decryptData(encrypted: ArrayBuffer, key: CryptoKey, iv: Uint8Array): Promise<ArrayBuffer> {
  return await window.crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: iv as unknown as BufferSource,
    },
    key,
    encrypted
  )
}

// 生成设备指纹（用于密钥派生）
export function generateDeviceFingerprint(): string {
  const components = [
    navigator.userAgent,
    navigator.language,
    new Date().getTimezoneOffset(),
    screen.width,
    screen.height,
  ]
  return components.join('|')
}

// 获取或创建加密盐
export function getOrCreateSalt(): Uint8Array {
  const stored = localStorage.getItem('encryption_salt')
  if (stored) {
    return new Uint8Array(JSON.parse(stored))
  }
  
  const salt = window.crypto.getRandomValues(new Uint8Array(16))
  localStorage.setItem('encryption_salt', JSON.stringify(Array.from(salt)))
  return salt
}
























