<template>
  <div class="legal-page">
    <div class="legal-container">
      <div class="legal-header">
        <div class="brand-mark">
          <span class="material-icons brand-icon">home_work</span>
        </div>
        <h1>Privacy Policy</h1>
        <p class="effective-date">Effective date: 28 April 2026</p>
      </div>

      <section>
        <p>
          ChoreSync ("we", "our", or "us") is a household chore management application. This Privacy
          Policy explains how we collect, use, and protect your personal information when you use
          ChoreSync at <strong>choresync-app.mahamadahir.com</strong> or via the ChoreSync mobile app.
        </p>
      </section>

      <section>
        <h2>1. Information We Collect</h2>
        <h3>Account information</h3>
        <p>
          When you create an account or sign in with Google or Microsoft, we receive your name, email
          address, and profile picture from those providers. We store this to identify you within the
          app and your household group.
        </p>
        <h3>Usage data</h3>
        <p>
          We collect information about how you interact with ChoreSync — tasks you create, complete,
          or snooze; groups you belong to; and chat messages sent to the AI assistant. This data is
          used solely to provide the service.
        </p>
        <h3>Calendar data</h3>
        <p>
          If you choose to connect Google Calendar or Microsoft Outlook, we access only the calendars
          you explicitly select. We use this to sync chore deadlines with your calendar. We do not read
          unrelated calendar events.
        </p>
        <h3>Device and notification data</h3>
        <p>
          With your permission, we store a push notification token to send you task reminders. You can
          revoke this permission at any time in your device settings.
        </p>
      </section>

      <section>
        <h2>2. How We Use Your Information</h2>
        <ul>
          <li>To provide and improve the ChoreSync service</li>
          <li>To send task reminders and household notifications</li>
          <li>To calculate household statistics, streaks, and leaderboards</li>
          <li>To power the AI assistant with context about your tasks and groups</li>
          <li>To contact you about important service changes</li>
        </ul>
        <p>We do not sell your personal data to third parties.</p>
      </section>

      <section>
        <h2>3. Third-Party Services</h2>
        <ul>
          <li>
            <strong>Google Sign-In / Google Calendar</strong> — governed by
            <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">Google's Privacy Policy</a>
          </li>
          <li>
            <strong>Microsoft Sign-In / Outlook Calendar</strong> — governed by
            <a href="https://privacy.microsoft.com/privacystatement" target="_blank" rel="noopener">Microsoft's Privacy Statement</a>
          </li>
          <li>
            <strong>Google Gemini AI</strong> — messages sent to the AI assistant may be processed by
            Google's Gemini API. We do not store raw AI conversations beyond your current session history.
          </li>
          <li>
            <strong>Expo / EAS</strong> — the mobile app is built and distributed via Expo Application
            Services, governed by
            <a href="https://expo.dev/privacy" target="_blank" rel="noopener">Expo's Privacy Policy</a>.
          </li>
        </ul>
      </section>

      <section>
        <h2>4. Data Retention</h2>
        <p>
          We retain your data for as long as your account is active. You may request deletion of your
          account and associated data at any time by emailing us at the address below. Deletion requests
          are processed within 30 days.
        </p>
      </section>

      <section>
        <h2>5. Data Security</h2>
        <p>
          All data is transmitted over HTTPS. Sensitive credentials (such as OAuth tokens) are stored
          encrypted. We follow industry-standard security practices, though no system is completely
          immune to breaches.
        </p>
      </section>

      <section>
        <h2>6. Children's Privacy</h2>
        <p>
          ChoreSync is not directed at children under 13. We do not knowingly collect personal
          information from children under 13. If you believe a child has provided us with personal
          information, please contact us to have it removed.
        </p>
      </section>

      <section>
        <h2>7. Changes to This Policy</h2>
        <p>
          We may update this Privacy Policy from time to time. We will notify you of significant changes
          by updating the effective date at the top of this page. Continued use of ChoreSync after
          changes constitutes acceptance of the updated policy.
        </p>
      </section>

      <section>
        <h2>8. Contact Us</h2>
        <p>
          If you have questions about this Privacy Policy or your data, please contact us at:<br />
          <a href="mailto:syncchore@gmail.com">syncchore@gmail.com</a>
        </p>
      </section>

      <div class="legal-footer">
        <router-link to="/terms">Terms of Service</router-link>
        <span>·</span>
        <router-link to="/login" class="signin-link">← Sign In</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.legal-page {
  min-height: 100vh;
  background: #fdfbf7;
  padding: 48px 20px;
  font-family: 'Inter', system-ui, sans-serif;
}
.legal-container {
  max-width: 720px;
  margin: 0 auto;
}
.legal-header {
  text-align: center;
  margin-bottom: 48px;
}
.brand-mark {
  width: 64px;
  height: 64px;
  background: #94433a;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}
.brand-icon {
  color: #fff;
  font-size: 32px;
}
h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 8px;
}
.effective-date {
  color: #888;
  font-size: 0.9rem;
}
section {
  margin-bottom: 36px;
}
h2 {
  font-size: 1.15rem;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e0db;
}
h3 {
  font-size: 1rem;
  font-weight: 600;
  color: #333;
  margin: 16px 0 6px;
}
p {
  color: #444;
  line-height: 1.75;
  margin: 0 0 12px;
}
ul {
  color: #444;
  line-height: 1.75;
  padding-left: 20px;
}
li {
  margin-bottom: 6px;
}
a {
  color: #94433a;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
.signin-link {
  font-weight: 700;
}
.legal-footer {
  display: flex;
  gap: 12px;
  justify-content: center;
  align-items: center;
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid #e8e0db;
  color: #888;
  font-size: 0.9rem;
}
</style>
