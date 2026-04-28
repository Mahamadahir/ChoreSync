<template>
  <div class="legal-page">
    <div class="legal-container">
      <div class="legal-header">
        <div class="brand-mark">
          <span class="material-icons brand-icon">home_work</span>
        </div>
        <h1>Terms of Service</h1>
        <p class="effective-date">Effective date: 28 April 2026</p>
      </div>

      <section>
        <p>
          By accessing or using ChoreSync ("the Service"), you agree to be bound by these Terms of
          Service. If you do not agree, please do not use the Service.
        </p>
      </section>

      <section>
        <h2>1. Use of the Service</h2>
        <p>
          ChoreSync is a household chore management application intended for personal, non-commercial
          use. You must be at least 13 years old to use the Service. You are responsible for maintaining
          the confidentiality of your account credentials.
        </p>
        <p>You agree not to:</p>
        <ul>
          <li>Use the Service for any unlawful purpose</li>
          <li>Attempt to access accounts or data that are not yours</li>
          <li>Interfere with or disrupt the integrity or performance of the Service</li>
          <li>Reverse-engineer or attempt to extract the source code of the Service</li>
        </ul>
      </section>

      <section>
        <h2>2. Accounts</h2>
        <p>
          You may register using an email and password, or via Google or Microsoft sign-in. You are
          responsible for all activity that occurs under your account. Please notify us immediately
          at <a href="mailto:syncchore@gmail.com">syncchore@gmail.com</a> if you suspect
          unauthorised access.
        </p>
      </section>

      <section>
        <h2>3. Groups and Household Data</h2>
        <p>
          When you create or join a household group, other members of that group can see tasks assigned
          to you, your completion history, and your display name. Group moderators can create, edit,
          and delete tasks visible to all group members.
        </p>
      </section>

      <section>
        <h2>4. AI Assistant</h2>
        <p>
          ChoreSync includes an AI assistant powered by Google Gemini. The assistant operates within
          the context of your tasks and groups. Do not share sensitive personal or financial information
          with the assistant. We are not liable for errors or actions taken based on AI responses.
        </p>
      </section>

      <section>
        <h2>5. Intellectual Property</h2>
        <p>
          The ChoreSync name, logo, and application design are the property of ChoreSync and its
          developers. The Service is provided for your personal use; you may not copy, distribute, or
          create derivative works without permission.
        </p>
      </section>

      <section>
        <h2>6. Disclaimers and Limitation of Liability</h2>
        <p>
          The Service is provided "as is" without warranties of any kind, express or implied. We do not
          guarantee that the Service will be uninterrupted, error-free, or free of viruses. To the
          fullest extent permitted by law, ChoreSync and its developers shall not be liable for any
          indirect, incidental, or consequential damages arising from your use of the Service.
        </p>
      </section>

      <section>
        <h2>7. Termination</h2>
        <p>
          We reserve the right to suspend or terminate your account at any time for violation of these
          Terms or for any other reason at our discretion. You may delete your account at any time by
          contacting us at <a href="mailto:syncchore@gmail.com">syncchore@gmail.com</a>.
        </p>
      </section>

      <section>
        <h2>8. Changes to These Terms</h2>
        <p>
          We may update these Terms from time to time. We will notify you of significant changes by
          updating the effective date. Continued use of the Service after changes constitutes your
          acceptance of the updated Terms.
        </p>
      </section>

      <section>
        <h2>9. Governing Law</h2>
        <p>
          These Terms are governed by applicable law. Any disputes shall be resolved in the jurisdiction
          where ChoreSync operates.
        </p>
      </section>

      <section>
        <h2>10. Contact</h2>
        <p>
          Questions about these Terms? Contact us at:
          <a href="mailto:syncchore@gmail.com">syncchore@gmail.com</a>
        </p>
      </section>

      <div class="legal-footer">
        <router-link to="/privacy">Privacy Policy</router-link>
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
