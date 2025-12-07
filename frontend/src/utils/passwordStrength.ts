export type PasswordStrength = {
  score: number; // 0..1
  label: 'Weak' | 'Medium' | 'Strong';
  color: 'red' | 'orange' | 'green' | 'grey';
};

export function evaluatePassword(pwd: string): PasswordStrength {
  if (!pwd) {
    return { score: 0, label: 'Weak', color: 'grey' };
  }

  let score = 0;
  if (pwd.length >= 8) score += 0.25;
  if (/[A-Z]/.test(pwd)) score += 0.2;
  if (/[a-z]/.test(pwd)) score += 0.2;
  if (/[0-9]/.test(pwd)) score += 0.15;
  if (/[^A-Za-z0-9]/.test(pwd)) score += 0.2;
  if (pwd.length >= 12) score += 0.1;

  const clamped = Math.min(score, 1);
  if (clamped >= 0.8) {
    return { score: clamped, label: 'Strong', color: 'green' };
  }
  if (clamped >= 0.5) {
    return { score: clamped, label: 'Medium', color: 'orange' };
  }
  return { score: clamped, label: 'Weak', color: 'red' };
}
