<template>
  <q-page class="q-pa-lg flex flex-center">
    <q-card class="q-pa-lg" style="max-width: 640px; width: 100%;">
      <div class="text-h5 q-mb-sm">Welcome to ChoreSync</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        You are signed in. Use the shortcuts below to manage your account or keep working.
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-card flat bordered class="q-pa-md">
            <div class="text-subtitle1 q-mb-xs">Profile</div>
            <div class="text-body2 text-grey-7 q-mb-sm">Update your email or password.</div>
            <q-btn to="/profile" color="primary" label="Go to Profile" unelevated />
          </q-card>
        </div>
        <div class="col-12 col-md-6">
          <q-card flat bordered class="q-pa-md">
            <div class="text-subtitle1 q-mb-xs">Calendar</div>
            <div class="text-body2 text-grey-7 q-mb-sm">View and manage your events/tasks.</div>
            <q-btn to="/calendar" color="secondary" label="Open Calendar" unelevated />
          </q-card>
        </div>
      </div>
    </q-card>
  </q-page>
</template>
