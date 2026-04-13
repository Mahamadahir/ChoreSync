<template>
  <div class="cs-page">
    <!-- Header -->
    <div v-if="group" class="cs-page-header">
      <div style="display:flex;align-items:center;gap:12px">
        <button class="cs-icon-btn" @click="$router.push({ name: 'groups' })">
          <span class="material-symbols-outlined">arrow_back</span>
        </button>
        <div>
          <div class="cs-page-title" style="margin:0">{{ group.name }}</div>
          <div style="font-size:12px;color:var(--cs-muted)">Code: <span style="font-family:monospace;font-weight:700">{{ group.group_code }}</span></div>
        </div>
      </div>
      <span
        class="cs-chip"
        :style="group.role === 'moderator'
          ? 'background:var(--cs-primary-container);color:var(--cs-primary)'
          : 'background:var(--cs-surface-high);color:var(--cs-muted)'"
      >{{ group.role }}</span>
    </div>

    <div v-if="error" class="cs-error-msg" style="margin-bottom:16px">{{ error }}</div>

    <div v-if="loading" style="display:flex;flex-direction:column;gap:12px">
      <div v-for="i in 3" :key="i" class="cs-skeleton" style="height:60px;border-radius:var(--cs-radius-md)" />
    </div>

    <template v-else-if="group">
      <!-- Tab pills -->
      <div class="cs-filter-tabs" style="margin-bottom:24px">
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'tasks' }]" @click="tab = 'tasks'" style="position:relative">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">task</span>
          Tasks
          <span v-if="tabBadge('tasks') > 0" class="cs-tab-badge">{{ tabBadge('tasks') }}</span>
        </button>
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'people' }]" @click="tab = 'people'" style="position:relative">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">people</span>
          People
          <span v-if="tabBadge('people') > 0" class="cs-tab-badge">{{ tabBadge('people') }}</span>
        </button>
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'discover' }]" @click="tab = 'discover'" style="position:relative">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">explore</span>
          Discover
          <span v-if="tabBadge('discover') > 0" class="cs-tab-badge">{{ tabBadge('discover') }}</span>
        </button>
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'chat' }]" @click="tab = 'chat'" style="position:relative">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">chat</span>
          Chat
          <span v-if="tabBadge('chat') > 0" class="cs-tab-badge">{{ tabBadge('chat') }}</span>
        </button>
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'settings' }]" @click="tab = 'settings'">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">settings</span>
          Settings
        </button>
        <button :class="['cs-filter-tab', { 'cs-filter-tab--active': tab === 'analytics' }]" @click="tab = 'analytics'">
          <span class="material-symbols-outlined" style="font-size:15px;vertical-align:-3px">bar_chart</span>
          Analytics
        </button>
      </div>

      <!-- ── TASKS ──────────────────────────────────────────── -->
      <div v-if="tab === 'tasks'">
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:12px">
          <!-- Moderators always see New Task. Members in restricted groups see Suggest Task. -->
          <button
            v-if="group.role === 'moderator' || !group.task_proposal_voting_required"
            class="cs-btn-primary"
            @click="showTemplateForm = true"
          >
            <span class="material-symbols-outlined">add_task</span>
            New Task
          </button>
          <button
            v-if="group.task_proposal_voting_required && group.role !== 'moderator'"
            class="cs-btn-outline"
            @click="showProposalForm = true"
          >
            <span class="material-symbols-outlined">lightbulb</span>
            Suggest Task
          </button>
        </div>

        <!-- Hidden file input for photo proof uploads -->
        <input
          ref="proofInputRef"
          type="file"
          accept="image/*"
          style="display:none"
          @change="handleProofFile"
        />

        <div v-if="tasks.length === 0" class="cs-empty">
          <span class="material-symbols-outlined">task_alt</span>
          <div class="cs-empty-sub">No tasks yet. Create the first one!</div>
        </div>

        <div v-else class="cs-card" style="padding:0;overflow:hidden">
          <div v-for="t in tasks" :key="t.id" class="cs-task-item" style="cursor:default">
            <div class="cs-task-body">
              <div class="cs-task-name">{{ t.template_name }}</div>
              <div class="cs-task-meta">
                <span>Due {{ formatDate(t.deadline) }}</span>
                <span>·</span>
                <span>{{ t.assigned_to_username ?? 'Unassigned' }}</span>
              </div>
              <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">
                <span :class="['cs-chip', statusChipClass(t.status)]">{{ t.status }}</span>
                <!-- Proof thumbnail -->
                <a v-if="t.photo_proof" :href="t.photo_proof" target="_blank" rel="noopener">
                  <img :src="t.photo_proof" alt="Proof" style="max-height:36px;border-radius:6px;cursor:pointer;vertical-align:middle" />
                </a>
                <span v-else-if="t.photo_proof_required && (t.status === 'pending' || t.status === 'snoozed')" style="font-size:12px;color:var(--cs-pending);display:flex;align-items:center;gap:3px">
                  <span class="material-symbols-outlined" style="font-size:14px">camera_alt</span>
                  Photo proof required
                </span>
              </div>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end;flex-shrink:0">
              <!-- Upload proof (only assigned user) -->
              <button
                v-if="t.photo_proof_required && !t.photo_proof && (t.status === 'pending' || t.status === 'snoozed') && String(t.assigned_to_id) === String(myUserId)"
                class="cs-btn-outline"
                style="padding:5px 12px;font-size:12px;gap:4px"
                :disabled="proofUploading[t.id]"
                @click="triggerProofUpload(t.id)"
              >
                <span class="material-symbols-outlined" style="font-size:15px">camera_alt</span>
                {{ proofUploading[t.id] ? 'Uploading…' : 'Upload Proof' }}
              </button>
              <!-- Complete (only assigned user) -->
              <button
                v-if="(t.status === 'pending' || t.status === 'snoozed') && String(t.assigned_to_id) === String(myUserId)"
                class="cs-btn-primary"
                style="padding:6px 14px;font-size:13px;gap:4px"
                :disabled="t.photo_proof_required && !t.photo_proof"
                :title="t.photo_proof_required && !t.photo_proof ? 'Upload photo proof first' : 'Mark complete'"
                @click="completeTask(t.id)"
              >
                <span class="material-symbols-outlined" style="font-size:16px">check_circle</span>
                Complete
              </button>
              <!-- Reopen (only assigned user) -->
              <button
                v-if="t.status === 'completed' && String(t.assigned_to_id) === String(myUserId)"
                class="cs-btn-outline"
                style="padding:6px 14px;font-size:13px;gap:4px;border-color:var(--cs-warning,#f59e0b);color:var(--cs-warning,#f59e0b)"
                @click="uncompleteTask(t.id)"
              >
                <span class="material-symbols-outlined" style="font-size:16px">undo</span>
                Reopen
              </button>
              <!-- Swap (only assigned user, active tasks) -->
              <button
                v-if="(t.status === 'pending' || t.status === 'snoozed') && String(t.assigned_to_id) === String(myUserId)"
                class="cs-btn-outline"
                style="padding:5px 12px;font-size:12px;gap:4px"
                @click="openSwapDialog(t)"
              >
                <span class="material-symbols-outlined" style="font-size:15px">swap_horiz</span>
                Swap
              </button>
              <!-- Marketplace (only assigned user) -->
              <button
                v-if="(t.status === 'pending' || t.status === 'snoozed') && String(t.assigned_to_id) === String(myUserId) && !t.on_marketplace"
                class="cs-btn-outline"
                style="padding:5px 12px;font-size:12px;gap:4px"
                @click="openListMarketplace(t)"
              >
                <span class="material-symbols-outlined" style="font-size:15px">storefront</span>
                List
              </button>
              <span v-if="t.on_marketplace" class="cs-chip" style="background:var(--cs-tertiary-container);color:var(--cs-tertiary)">Marketplace</span>
              <!-- Why assigned? -->
              <button
                v-if="t.assigned_to_id"
                class="cs-btn-outline"
                style="padding:5px 12px;font-size:12px;gap:4px;border-color:var(--cs-outline-variant)"
                @click="toggleBreakdown(t.id)"
              >
                <span class="material-symbols-outlined" style="font-size:15px">analytics</span>
                Why assigned?
              </button>
            </div>
            <!-- Breakdown panel (lazy loaded, shown inline below the task row) -->
            <div v-if="expandedBreakdown === t.id" style="margin-top:10px;border-top:1px solid var(--cs-outline-variant);padding-top:10px">
              <div v-if="breakdownLoading[t.id]" style="font-size:12px;color:var(--cs-muted);padding:4px 0">Loading breakdown…</div>
              <template v-else-if="breakdownCache[t.id]">
                <template v-if="breakdownCache[t.id].breakdown_available">
                  <div style="font-size:11px;font-weight:700;letter-spacing:0.8px;color:var(--cs-muted);margin-bottom:8px">ASSIGNMENT SCORES — lower = higher priority</div>
                  <div
                    v-for="c in breakdownCache[t.id].candidates"
                    :key="c.user_id"
                    style="margin-bottom:8px"
                  >
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                      <div style="width:18px;height:18px;border-radius:50%;background:var(--cs-surface-high);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:var(--cs-muted);flex-shrink:0">
                        {{ c.username[0].toUpperCase() }}
                      </div>
                      <span style="font-size:13px;font-weight:600;color:var(--cs-on-surface)">{{ c.username }}<span v-if="c.is_me"> (you)</span></span>
                      <span v-if="c.is_winner" style="font-size:9px;font-weight:700;letter-spacing:0.8px;padding:2px 6px;border-radius:4px;background:var(--cs-secondary);color:#fff">ASSIGNED</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px">
                      <div style="flex:1;height:8px;background:var(--cs-surface-high);border-radius:4px;overflow:hidden">
                        <div :style="{
                          width: Math.round(c.final_score / Math.max(...breakdownCache[t.id].candidates.map(x => x.final_score), 1) * 100) + '%',
                          height: '100%',
                          borderRadius: '4px',
                          background: c.is_winner ? 'var(--cs-secondary)' : 'var(--cs-primary-container)',
                        }" />
                      </div>
                      <span style="font-size:12px;font-weight:700;color:var(--cs-muted);width:28px;text-align:right">{{ c.final_score }}</span>
                    </div>
                    <!-- My components (only for own row) -->
                    <div v-if="c.is_me && c.components" style="margin-top:6px;padding:10px;background:var(--cs-surface-low);border-radius:8px;border:1px solid var(--cs-outline-variant);font-size:11px;color:var(--cs-on-surface-variant);display:flex;flex-direction:column;gap:4px">
                      <div><strong>Fairness score:</strong> {{ c.components.stage1_score }} — task count (40%), difficulty-weighted time (35%), points (25%)</div>
                      <div><strong>Preference:</strong> {{ c.components.pref_multiplier <= 0.85 ? 'Prefer ×0.8' : c.components.pref_multiplier >= 1.15 ? 'Avoid ×1.2' : 'Neutral ×1.0' }}</div>
                      <div><strong>History affinity:</strong> {{ c.components.affinity_multiplier <= 0.9 ? 'High completion ×0.88' : c.components.affinity_multiplier >= 1.1 ? 'Low completion ×1.12' : 'No adjustment' }}</div>
                      <div><strong>Calendar penalty:</strong> +{{ c.components.calendar_penalty }}</div>
                    </div>
                  </div>
                </template>
                <div v-else style="font-size:12px;color:var(--cs-muted);font-style:italic">Score history not available for assignments made before this feature was added.</div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ── PEOPLE ─────────────────────────────────────────── -->
      <div v-if="tab === 'people'">
        <!-- Members grid -->
        <div class="cs-section-title">Members</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-bottom:28px">
          <div v-for="m in members" :key="m.user_id" class="cs-card">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <div class="cs-user-avatar" style="width:40px;height:40px;font-size:15px">
                {{ (m.username || 'U').slice(0, 2).toUpperCase() }}
              </div>
              <div>
                <div style="font-size:14px;font-weight:700">{{ m.username }}</div>
                <div style="font-size:11px;color:var(--cs-muted)">{{ m.email }}</div>
              </div>
            </div>
            <span
              class="cs-chip"
              :style="m.role === 'moderator'
                ? 'background:var(--cs-primary-container);color:var(--cs-primary)'
                : 'background:var(--cs-surface-high);color:var(--cs-muted)'"
            >{{ m.role }}</span>
            <div v-if="m.stats" style="margin-top:10px;font-size:12px;color:var(--cs-on-surface-variant);display:flex;gap:10px;flex-wrap:wrap">
              <span>✅ {{ m.stats.total_tasks_completed }}</span>
              <span>⭐ {{ m.stats.total_points }} pts</span>
              <span>🔥 {{ m.stats.current_streak_days }}d</span>
            </div>
          </div>
        </div>

        <!-- Leaderboard -->
        <div class="cs-section-title">Leaderboard</div>
        <div class="cs-card" style="padding:0;overflow:hidden;max-width:700px;margin-bottom:20px">
          <div
            v-for="(row, idx) in leaderboard"
            :key="row.user_id"
            style="display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--cs-outline-variant)"
          >
            <div style="width:28px;text-align:center;font-size:16px;font-weight:800;color:var(--cs-muted)">
              {{ idx + 1 === 1 ? '🥇' : idx + 1 === 2 ? '🥈' : idx + 1 === 3 ? '🥉' : idx + 1 }}
            </div>
            <div class="cs-user-avatar">{{ (row.username || 'U').slice(0, 2).toUpperCase() }}</div>
            <div style="flex:1">
              <div style="font-size:14px;font-weight:600">{{ row.username }}</div>
            </div>
            <div style="text-align:right;font-size:13px;color:var(--cs-on-surface-variant)">
              <div style="font-weight:700;color:var(--cs-tertiary)">⭐ {{ row.total_points }}</div>
              <div style="font-size:11px">{{ row.total_tasks_completed }} tasks · {{ Math.round(row.on_time_completion_rate * 100) }}% on-time</div>
            </div>
          </div>
        </div>

        <div v-if="leaderboard.length > 0" class="cs-card" style="max-width:700px">
          <FairnessChart :distribution="leaderboard" />
        </div>

        <!-- Invite (moderator only) -->
        <template v-if="group.role === 'moderator'">
          <div class="cs-section-title" style="margin-top:24px">Invite Member</div>
          <div class="cs-card" style="max-width:480px">
            <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
              <div style="flex:1;min-width:180px">
                <label class="cs-form-label">Email</label>
                <input v-model="invite.email" class="cs-form-input" type="email" placeholder="member@example.com" />
              </div>
              <!-- Flatshare: no role picker — everyone joins as housemate (moderator) -->
              <div v-if="group.group_type !== 'flatshare'" style="width:160px">
                <label class="cs-form-label">{{ inviteRoleLabel }}</label>
                <q-select v-model="invite.role" :options="inviteRoleOptions" option-value="value" option-label="label" emit-value map-options outlined dense />
              </div>
              <button class="cs-btn-primary" style="padding:10px 18px" :disabled="invite.loading" @click="inviteMember">
                <span class="material-symbols-outlined" style="font-size:18px">person_add</span>
                {{ invite.loading ? 'Sending…' : 'Invite' }}
              </button>
            </div>
            <div v-if="group.group_type === 'flatshare'" style="font-size:12px;color:var(--cs-muted);margin-top:4px">
              All housemates join with full access.
            </div>
            <div v-if="invite.message" style="margin-top:8px;font-size:13px" :style="invite.error ? 'color:var(--cs-error)' : 'color:var(--cs-secondary)'">
              {{ invite.message }}
            </div>
          </div>
        </template>

        <!-- Leave group -->
        <div style="margin-top:20px">
          <button
            class="cs-btn-outline"
            style="border-color:var(--cs-error);color:var(--cs-error);gap:6px"
            :disabled="leaveLoading"
            @click="leaveGroup"
          >
            <span class="material-symbols-outlined" style="font-size:18px">exit_to_app</span>
            Leave group
          </button>
          <div v-if="leaveError" style="margin-top:6px;font-size:12px;color:var(--cs-error)">{{ leaveError }}</div>
        </div>
      </div>

      <!-- ── DISCOVER ────────────────────────────────────────── -->
      <div v-if="tab === 'discover'">
        <!-- Marketplace -->
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <div class="cs-section-title" style="margin:0">Marketplace</div>
          <button class="cs-icon-btn" @click="loadMarketplace" title="Refresh">
            <span class="material-symbols-outlined">refresh</span>
          </button>
        </div>

        <div v-if="marketplaceLoading" style="display:flex;flex-direction:column;gap:10px;margin-bottom:24px">
          <div v-for="i in 3" :key="i" class="cs-skeleton" style="height:60px;border-radius:var(--cs-radius-md)" />
        </div>
        <div v-else-if="marketplaceListings.length === 0" class="cs-empty" style="padding:32px 0;margin-bottom:24px">
          <span class="material-symbols-outlined">storefront</span>
          <div class="cs-empty-sub">No tasks listed yet — list one from My Tasks!</div>
        </div>
        <div v-else class="cs-card" style="padding:0;overflow:hidden;margin-bottom:24px">
          <div v-for="listing in marketplaceListings" :key="listing.id" style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:16px 20px;border-bottom:1px solid var(--cs-outline-variant)">
            <div>
              <div style="font-size:14px;font-weight:600;margin-bottom:3px">{{ listing.task_name }}</div>
              <div style="font-size:12px;color:var(--cs-muted)">
                By {{ listing.listed_by_username }} · Due {{ formatDate(listing.deadline) }}
              </div>
              <span v-if="listing.bonus_points > 0" class="cs-chip" style="margin-top:6px;background:var(--cs-tertiary-container);color:var(--cs-tertiary)">
                +{{ listing.bonus_points }} pts bonus
              </span>
            </div>
            <div style="flex-shrink:0">
              <button
                v-if="listing.listed_by_id !== myUserId"
                class="cs-btn-primary"
                style="padding:7px 16px;font-size:13px"
                :disabled="claimingListing[listing.id]"
                @click="claimListing(listing.id)"
              >
                {{ claimingListing[listing.id] ? 'Claiming…' : 'Claim' }}
              </button>
              <button
                v-else
                class="cs-btn-outline"
                style="padding:7px 14px;font-size:13px;gap:4px;border-color:var(--cs-error);color:var(--cs-error)"
                :disabled="cancellingListing[listing.id]"
                @click="cancelListing(listing.id)"
              >
                {{ cancellingListing[listing.id] ? 'Removing…' : 'Remove' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Task Suggestions / Proposals -->
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <div class="cs-section-title" style="margin:0">
            {{ group.task_proposal_voting_required ? 'Pending Approvals' : 'Task Suggestions' }}
          </div>
          <button class="cs-btn-primary" style="padding:7px 14px;font-size:13px;gap:4px" @click="showProposalForm = true">
            <span class="material-symbols-outlined" style="font-size:16px">lightbulb</span>
            Suggest Task
          </button>
        </div>

        <div v-if="proposals.length === 0" class="cs-empty" style="padding:32px 0">
          <span class="material-symbols-outlined">lightbulb</span>
          <div class="cs-empty-sub">No suggestions yet.</div>
        </div>
        <div v-else style="display:flex;flex-direction:column;gap:10px">
          <div v-for="p in proposals" :key="p.id" class="cs-card">
            <!-- Header -->
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:6px">
              <div>
                <div style="font-size:14px;font-weight:700">{{ p.proposed_payload?.name ?? 'Unnamed task' }}</div>
                <div style="font-size:12px;color:var(--cs-muted);margin-top:2px">
                  Suggested by {{ p.proposed_by }} · {{ formatDate(p.created_at) }}
                </div>
              </div>
              <span class="cs-chip" :class="proposalChipClass(p.state)">{{ p.state }}</span>
            </div>

            <!-- Proposer details -->
            <div v-if="p.reason" style="font-size:13px;color:var(--cs-on-surface-variant);margin-bottom:8px">
              "{{ p.reason }}"
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
              <span class="cs-chip cs-chip--snoozed">{{ p.proposed_payload?.category }}</span>
              <span class="cs-chip cs-chip--snoozed">{{ p.proposed_payload?.recurring_choice }}</span>
              <span v-if="p.proposed_payload?.recur_value" class="cs-chip cs-chip--snoozed">every {{ p.proposed_payload.recur_value }}d</span>
              <span class="cs-chip cs-chip--snoozed">~{{ p.proposed_payload?.estimated_mins }}min</span>
            </div>

            <!-- Moderator edits diff -->
            <div v-if="p.payload_diff && Object.keys(p.payload_diff).length" style="background:var(--cs-surface-container);border-radius:8px;padding:8px 12px;margin-bottom:8px;font-size:12px">
              <div style="font-weight:600;margin-bottom:4px;color:var(--cs-on-surface-variant)">Moderator adjusted:</div>
              <div v-for="(change, field) in p.payload_diff" :key="field" style="color:var(--cs-on-surface-variant)">
                <strong>{{ field }}</strong>: <s style="color:var(--cs-error)">{{ change.from }}</s> → <span style="color:var(--cs-secondary)">{{ change.to }}</span>
              </div>
              <div v-if="p.approval_note" style="margin-top:4px;font-style:italic">"{{ p.approval_note }}"</div>
            </div>
            <div v-else-if="p.approval_note && p.state !== 'pending'" style="font-size:12px;color:var(--cs-muted);margin-bottom:8px;font-style:italic">
              Note: "{{ p.approval_note }}"
            </div>

            <!-- Moderator approve/reject actions -->
            <div v-if="p.state === 'pending' && group.role === 'moderator'" style="display:flex;gap:8px;flex-wrap:wrap">
              <button
                class="cs-btn-primary"
                style="padding:6px 16px;font-size:13px"
                :disabled="proposalAction[p.id]"
                @click="openApproveDialog(p)"
              >{{ proposalAction[p.id] === 'approving' ? 'Approving…' : 'Approve' }}</button>
              <button
                class="cs-btn-outline"
                style="padding:6px 14px;font-size:13px;border-color:var(--cs-error);color:var(--cs-error)"
                :disabled="proposalAction[p.id]"
                @click="openRejectDialog(p)"
              >{{ proposalAction[p.id] === 'rejecting' ? 'Rejecting…' : 'Reject' }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── SETTINGS ────────────────────────────────────────── -->
      <div v-if="tab === 'settings'">
        <!-- Group settings (moderator only) -->
        <template v-if="group.role === 'moderator'">
          <div class="cs-section-title">Group Configuration</div>
          <div class="cs-card" style="max-width:440px;margin-bottom:20px">
            <q-toggle v-model="settings.photo_proof_required" label="Require photo proof on task completion" class="q-mb-sm" />
            <q-toggle v-model="settings.task_proposal_voting_required" label="Restrict task creation to moderators (members suggest, moderators approve)" />
            <div style="margin-top:16px">
              <button class="cs-btn-primary" :disabled="settings.loading" @click="saveSettings">
                {{ settings.loading ? 'Saving…' : 'Save Settings' }}
              </button>
            </div>
            <div v-if="settings.message" style="margin-top:8px;font-size:12px" :style="settings.error ? 'color:var(--cs-error)' : 'color:var(--cs-secondary)'">
              {{ settings.message }}
            </div>
          </div>

          <!-- Task templates -->
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
            <div class="cs-section-title" style="margin:0">Task Templates</div>
            <button class="cs-btn-primary" style="padding:7px 14px;font-size:13px;gap:4px" @click="showTemplateForm = true">
              <span class="material-symbols-outlined" style="font-size:16px">add</span>
              New Template
            </button>
          </div>
          <div v-if="templates.length === 0" style="font-size:13px;color:var(--cs-muted)">No templates yet.</div>
          <div v-else class="cs-card" style="padding:0;overflow:hidden;max-width:560px">
            <div v-for="tmpl in templates" :key="tmpl.id" style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid var(--cs-outline-variant)">
              <div>
                <div style="font-size:14px;font-weight:600">{{ tmpl.name }}</div>
                <div style="font-size:11px;color:var(--cs-muted)">{{ tmpl.category }} · {{ tmpl.recurring_choice }}</div>
              </div>
              <button class="cs-icon-btn" style="color:var(--cs-error)" @click="deleteTemplate(tmpl.id)" title="Delete template">
                <span class="material-symbols-outlined">delete</span>
              </button>
            </div>
          </div>
        </template>

      </div>

      <!-- ── ANALYTICS ─────────────────────────────────────── -->
      <div v-if="tab === 'analytics'">
        <div v-if="analyticsLoading" style="display:flex;flex-direction:column;gap:12px">
          <div v-for="i in 4" :key="i" class="cs-skeleton" style="height:80px;border-radius:var(--cs-radius-md)" />
        </div>
        <div v-else-if="analyticsError" class="cs-error-msg">{{ analyticsError }}</div>
        <template v-else-if="groupStats">
          <!-- Summary row -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px">
            <div class="cs-card" style="text-align:center;padding:18px 12px">
              <div style="font-size:28px;font-weight:800;color:var(--cs-primary)">{{ Math.round(groupStats.completion_rate * 100) }}%</div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.8px;color:var(--cs-muted);margin-top:4px">COMPLETION RATE</div>
            </div>
            <div class="cs-card" style="text-align:center;padding:18px 12px">
              <div style="font-size:28px;font-weight:800;color:var(--cs-secondary)">{{ groupStats.completed_tasks }}</div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.8px;color:var(--cs-muted);margin-top:4px">COMPLETED</div>
            </div>
            <div class="cs-card" style="text-align:center;padding:18px 12px">
              <div style="font-size:28px;font-weight:800;color:var(--cs-on-surface)">{{ groupStats.resolved_tasks }}</div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.8px;color:var(--cs-muted);margin-top:4px">TOTAL DUE</div>
            </div>
            <div v-if="groupStats.most_completed_task" class="cs-card" style="padding:18px 12px">
              <div style="font-size:11px;font-weight:700;letter-spacing:0.8px;color:var(--cs-muted);margin-bottom:6px">TOP TASK</div>
              <div style="font-size:14px;font-weight:700;color:var(--cs-on-surface)">{{ groupStats.most_completed_task.name }}</div>
              <div style="font-size:12px;color:var(--cs-muted);margin-top:2px">{{ groupStats.most_completed_task.count }}× completed</div>
            </div>
          </div>

          <!-- Fairness distribution -->
          <div class="cs-section-title">Workload Distribution</div>
          <div class="cs-card" style="padding:0;overflow:hidden;margin-bottom:24px">
            <div
              v-for="(row, idx) in groupStats.fairness_distribution"
              :key="row.user_id"
              style="display:flex;align-items:center;gap:14px;padding:14px 16px;border-bottom:1px solid var(--cs-outline-variant)"
            >
              <div style="width:28px;height:28px;border-radius:50%;background:var(--cs-surface-high);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--cs-muted);flex-shrink:0">
                {{ (idx as number) + 1 }}
              </div>
              <div style="flex:1;min-width:0">
                <div style="font-size:14px;font-weight:600;color:var(--cs-on-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ row.username }}</div>
                <div style="display:flex;gap:10px;margin-top:3px;flex-wrap:wrap">
                  <span style="font-size:11px;color:var(--cs-muted)">✅ {{ row.total_tasks_completed }}</span>
                  <span style="font-size:11px;color:var(--cs-muted)">⭐ {{ row.total_points }} pts</span>
                  <span style="font-size:11px;color:var(--cs-muted)">🔥 {{ row.current_streak_days }}d streak</span>
                  <span style="font-size:11px;color:var(--cs-muted)">⏱ {{ Math.round(row.on_time_completion_rate * 100) }}% on-time</span>
                </div>
              </div>
              <!-- Mini bar: on-time rate -->
              <div style="width:64px;flex-shrink:0">
                <div style="height:6px;background:var(--cs-surface-high);border-radius:3px;overflow:hidden">
                  <div :style="{ width: Math.round(row.on_time_completion_rate * 100) + '%', height: '100%', background: 'var(--cs-secondary)', borderRadius: '3px' }" />
                </div>
              </div>
            </div>
          </div>

          <!-- Assignment fairness matrix -->
          <template v-if="assignmentMatrix && Object.keys(assignmentMatrix).length > 0">
            <div class="cs-section-title">Assignment Priority</div>
            <div style="font-size:12px;color:var(--cs-muted);margin-bottom:10px">Lower score = next in line for task assignment. Blends task count (40%), difficulty-weighted time burden (35%), and points (25%).</div>
            <div class="cs-card" style="padding:0;overflow:hidden;margin-bottom:24px">
              <div
                v-for="[uid, score] in matrixSorted"
                :key="uid"
                style="display:flex;align-items:center;gap:14px;padding:12px 16px;border-bottom:1px solid var(--cs-outline-variant)"
              >
                <div style="width:120px;flex-shrink:0;font-size:13px;font-weight:600;color:var(--cs-on-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                  {{ memberNameMap[uid] ?? uid.slice(0, 8) }}
                </div>
                <div style="flex:1;height:10px;background:var(--cs-surface-high);border-radius:5px;overflow:hidden">
                  <div :style="{ width: Math.round((score as number) * 100) + '%', height: '100%', borderRadius: '5px', background: score < 0.4 ? 'var(--cs-secondary)' : score < 0.7 ? 'var(--cs-tertiary)' : 'var(--cs-primary)' }" />
                </div>
                <div style="width:36px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--cs-muted);text-align:right">
                  {{ Math.round((score as number) * 100) }}
                </div>
              </div>
            </div>
          </template>

          <!-- Preference Compliance -->
          <template v-if="groupStats.preference_compliance && groupStats.preference_compliance.length > 0">
            <div class="cs-section-title">Preference Compliance</div>
            <div style="font-size:12px;color:var(--cs-muted);margin-bottom:10px">How often are members assigned tasks they marked as 'avoid'. Lower avoid % = better compliance.</div>
            <div class="cs-card" style="padding:0;overflow:hidden;margin-bottom:24px">
              <div
                v-for="row in groupStats.preference_compliance"
                :key="row.user_id"
                style="display:flex;align-items:flex-start;gap:14px;padding:14px 16px;border-bottom:1px solid var(--cs-outline-variant)"
              >
                <div style="flex:1;min-width:0">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span style="font-size:14px;font-weight:600;color:var(--cs-on-surface)">{{ row.username }}</span>
                    <span
                      v-if="row.avoid_pct > 0.15"
                      style="font-size:10px;font-weight:700;letter-spacing:0.6px;padding:2px 7px;border-radius:4px;background:var(--cs-error-container);color:var(--cs-error)"
                    >{{ Math.round(row.avoid_pct * 100) }}% AVOID</span>
                    <span
                      v-else-if="row.total_assignments === 0"
                      style="font-size:10px;color:var(--cs-muted)"
                    >No assignments yet</span>
                  </div>
                  <div v-if="row.total_assignments > 0" style="display:flex;gap:4px;height:8px;border-radius:4px;overflow:hidden;max-width:200px">
                    <div
                      v-if="row.prefer_count > 0"
                      :style="{ flex: row.prefer_count, background: 'var(--cs-secondary)', minWidth: '4px' }"
                      :title="`Prefer: ${row.prefer_count}`"
                    />
                    <div
                      v-if="row.neutral_count + row.unset_count > 0"
                      :style="{ flex: row.neutral_count + row.unset_count, background: 'var(--cs-surface-high)', minWidth: '4px' }"
                      :title="`Neutral/unset: ${row.neutral_count + row.unset_count}`"
                    />
                    <div
                      v-if="row.avoid_count > 0"
                      :style="{ flex: row.avoid_count, background: 'var(--cs-error)', minWidth: '4px' }"
                      :title="`Avoid: ${row.avoid_count}`"
                    />
                  </div>
                  <div v-if="row.total_assignments > 0" style="font-size:11px;color:var(--cs-muted);margin-top:4px;display:flex;gap:10px;flex-wrap:wrap">
                    <span v-if="row.prefer_count > 0" style="color:var(--cs-secondary)">✓ {{ row.prefer_count }} preferred</span>
                    <span>· {{ row.neutral_count + row.unset_count }} neutral</span>
                    <span v-if="row.avoid_count > 0" style="color:var(--cs-error)">✗ {{ row.avoid_count }} avoided</span>
                    <span style="color:var(--cs-muted)">/ {{ row.total_assignments }} total</span>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>

      <!-- ── CHAT ───────────────────────────────────────────── -->
      <div v-if="tab === 'chat'" style="display:flex;flex-direction:column;height:calc(100vh - 280px);min-height:400px">
        <div class="cs-card" style="padding:0;overflow:hidden;flex:1;display:flex;flex-direction:column">
          <div class="cs-chat-messages" ref="chatBox" @click.self="receiptPopoverMsgId = null" style="flex:1;overflow-y:auto">
            <div v-if="chatMessages.length === 0" style="text-align:center;padding:32px;color:var(--cs-muted);font-size:13px">
              No messages yet. Say hello!
            </div>
            <div
              v-for="(msg, i) in chatMessages"
              :key="i"
              :class="['cs-chat-bubble', String(msg.sender_id) === String(myUserId) ? 'cs-chat-bubble--self' : 'cs-chat-bubble--other']"
            >
              <div class="cs-chat-meta">{{ msg.username }} · {{ formatDate(msg.sent_at) }}</div>
              <div class="cs-chat-text" v-html="renderChatBody(msg.body)" />
              <!-- Tick + reader popover (own messages only) -->
              <div v-if="String(msg.sender_id) === String(myUserId)" class="cs-chat-tick-wrap">
                <button
                  class="cs-chat-tick"
                  :class="{
                    'cs-chat-tick--some': msg.read_by?.length > 0 && !msg.all_read,
                    'cs-chat-tick--all':  msg.all_read,
                  }"
                  :title="msg.read_by?.length ? 'Click to see who read this' : 'Sent'"
                  @click="receiptPopoverMsgId = receiptPopoverMsgId === msg.id ? null : msg.id"
                >
                  <span class="material-symbols-outlined">{{ msg.read_by?.length > 0 ? 'done_all' : 'done' }}</span>
                </button>
                <!-- Popover -->
                <div v-if="receiptPopoverMsgId === msg.id" class="cs-receipt-popover">
                  <div v-if="!msg.read_by?.length" style="font-size:12px;color:var(--cs-muted)">Not yet read</div>
                  <div v-for="r in msg.read_by" :key="r.user_id" class="cs-receipt-row">
                    <span class="material-symbols-outlined" style="font-size:13px;color:var(--cs-primary);font-variation-settings:'FILL' 1,'wght' 500,'GRAD' 0,'opsz' 16">done_all</span>
                    <span style="font-size:12px;font-weight:600">{{ r.username }}</span>
                    <span style="font-size:11px;color:var(--cs-muted);margin-left:auto">{{ formatDate(r.seen_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- @mention autocomplete dropdown -->
          <div v-if="mentionDropdown.length > 0" class="cs-mention-dropdown">
            <button
              v-for="m in mentionDropdown"
              :key="m.value"
              class="cs-mention-item"
              @mousedown.prevent="insertMention(m.value)"
            >
              <span class="cs-mention-badge">@</span>
              <span>{{ m.label }}</span>
            </button>
          </div>
          <div class="cs-chat-input-row">
            <input
              ref="chatInputEl"
              v-model="chatInput"
              class="cs-form-input"
              style="flex:1;border-radius:var(--cs-radius-xl)"
              placeholder="Type a message… use @ to mention"
              @keyup.enter="sendMessage"
              @input="onChatInput"
              @keydown="onChatKeydown"
            />
            <button class="cs-btn-primary" style="padding:10px 16px" @click="sendMessage">
              <span class="material-symbols-outlined">send</span>
            </button>
          </div>
        </div>
      </div>

    </template>

    <!-- List on Marketplace dialog -->
    <q-dialog v-model="listMarketplaceDialog.show">
      <q-card style="min-width:340px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">List on Marketplace</div>
          <div style="font-size:13px;color:var(--cs-muted)">{{ listMarketplaceDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section>
          <div style="font-size:12px;color:var(--cs-on-surface-variant);margin-bottom:10px">
            Your balance: <strong style="color:var(--cs-tertiary)">⭐ {{ myPoints }}</strong>
          </div>
          <q-input
            v-model.number="listMarketplaceDialog.bonusPoints"
            type="number"
            label="Bonus points to offer"
            :hint="`From your own balance — max ${myPoints} pts`"
            outlined
            min="0"
            :max="myPoints"
            :error="listMarketplaceDialog.bonusPoints > myPoints"
            :error-message="`You only have ${myPoints} points`"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn
            color="primary"
            label="List Task"
            :loading="listMarketplaceDialog.loading"
            :disable="listMarketplaceDialog.bonusPoints > myPoints"
            @click="submitListMarketplace"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Swap dialog -->
    <q-dialog v-model="swapDialog.show">
      <q-card style="min-width:340px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Request Swap</div>
          <div style="font-size:13px;color:var(--cs-muted)">{{ swapDialog.task?.template_name }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-select
            v-model="swapDialog.targetUserId"
            :options="swappableMembers"
            option-value="value"
            option-label="label"
            emit-value
            map-options
            label="Swap with (optional — leave blank to broadcast)"
            outlined
            clearable
          />
          <q-input
            v-model="swapDialog.reason"
            label="Reason (optional)"
            outlined
            type="textarea"
            rows="2"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Send Request" :loading="swapDialog.loading" @click="submitSwap" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Suggest Task dialog -->
    <q-dialog v-model="showProposalForm">
      <q-card style="min-width:400px;max-width:520px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Suggest a Task</div>
          <div style="font-size:13px;color:var(--cs-muted)">A moderator will review and approve your suggestion.</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model="proposalForm.name" label="Task name *" outlined />
          <q-select v-model="proposalForm.category" :options="categoryOptions" label="Category" outlined emit-value map-options />
          <q-select v-model="proposalForm.recurring_choice" :options="recurrenceOptions" label="Recurrence" outlined emit-value map-options />
          <q-input
            v-if="proposalForm.recurring_choice === 'every_n_days'"
            v-model.number="proposalForm.recur_value"
            type="number" label="Repeat every N days" outlined min="1"
          />
          <q-input v-model.number="proposalForm.difficulty" type="number" label="Difficulty (1–5)" outlined min="1" max="5" />
          <q-input v-model.number="proposalForm.estimated_mins" type="number" label="Estimated minutes" outlined min="5" />
          <q-input
            v-model="proposalForm.due_datetime"
            type="datetime-local"
            :label="proposalForm.recurring_choice === 'none' ? 'Due date & time' : 'First occurrence'"
            outlined
          />
          <q-input v-model="proposalForm.reason" label="Why is this needed? (optional)" outlined type="textarea" rows="2" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Submit Suggestion" :loading="proposalForm.loading" @click="submitProposal" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Approve dialog (moderator, with optional edit) -->
    <q-dialog v-model="approveDialog.show">
      <q-card style="min-width:400px;max-width:520px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Approve Suggestion</div>
          <div style="font-size:13px;color:var(--cs-muted)">Edit any fields before approving, or approve as-is.</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model="approveDialog.name" label="Task name" outlined />
          <q-select v-model="approveDialog.category" :options="categoryOptions" label="Category" outlined emit-value map-options />
          <q-select v-model="approveDialog.recurring_choice" :options="recurrenceOptions" label="Recurrence" outlined emit-value map-options />
          <q-input
            v-if="approveDialog.recurring_choice === 'every_n_days'"
            v-model.number="approveDialog.recur_value"
            type="number" label="Repeat every N days" outlined min="1"
          />
          <q-input v-model.number="approveDialog.difficulty" type="number" label="Difficulty (1–5)" outlined min="1" max="5" />
          <q-input v-model.number="approveDialog.estimated_mins" type="number" label="Estimated minutes" outlined min="5" />
          <q-input v-model="approveDialog.due_datetime" type="datetime-local" label="First occurrence" outlined />
          <q-input v-model="approveDialog.approval_note" label="Note to proposer (optional)" outlined type="textarea" rows="2" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Approve" :loading="approveDialog.loading" @click="submitApprove" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Reject dialog -->
    <q-dialog v-model="rejectDialog.show">
      <q-card style="min-width:340px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">Decline Suggestion</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="rejectDialog.note" label="Reason for declining (optional)" outlined type="textarea" rows="2" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="negative" label="Decline" :loading="rejectDialog.loading" @click="submitReject" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- New task dialog -->
    <q-dialog v-model="showTemplateForm">
      <q-card style="min-width:420px;background:var(--cs-surface-low)">
        <q-card-section>
          <div style="font-size:16px;font-weight:700">New Task</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model="templateForm.name" label="Name" outlined />
          <q-select v-model="templateForm.category" :options="categoryOptions" label="Category" outlined emit-value map-options />
          <q-select v-model="templateForm.recurring_choice" :options="recurrenceOptions" label="Recurrence" outlined emit-value map-options />
          <q-select v-model="templateForm.importance" :options="importanceOptions" label="Importance" outlined emit-value map-options />
          <q-input v-model.number="templateForm.difficulty" type="number" label="Difficulty (1–5)" outlined min="1" max="5" />
          <q-input
            v-model="templateForm.due_datetime"
            type="datetime-local"
            :label="templateForm.recurring_choice === 'none' ? 'Due date & time' : 'First due date & time'"
            outlined
          />
          <q-input
            v-if="templateForm.recurring_choice === 'every_n_days'"
            v-model.number="templateForm.recur_value"
            type="number" label="Repeat every N days" outlined min="1"
          />
          <q-select
            v-if="templateForm.recurring_choice === 'custom'"
            v-model="templateForm.days_of_week"
            :options="[
              { label: 'Mon', value: 'mon' }, { label: 'Tue', value: 'tue' },
              { label: 'Wed', value: 'wed' }, { label: 'Thu', value: 'thu' },
              { label: 'Fri', value: 'fri' }, { label: 'Sat', value: 'sat' },
              { label: 'Sun', value: 'sun' },
            ]"
            label="Days of week" outlined multiple emit-value map-options
          />
          <q-toggle v-model="templateForm.photo_proof_required" label="Photo proof required" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Create" :loading="templateForm.loading" @click="submitTemplate" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ── Post-completion preference nudge ─────────────────── -->
    <q-dialog v-model="prefNudge.show" persistent>
      <q-card style="min-width:320px;max-width:420px;border-radius:20px;padding:8px">
        <q-card-section>
          <div style="font-size:20px;font-weight:800;margin-bottom:4px">How was this task?</div>
          <div style="font-size:13px;color:var(--cs-muted)">
            <strong>{{ prefNudge.taskName }}</strong> — your answer helps us assign tasks fairly next time.
          </div>
        </q-card-section>
        <q-card-section style="display:flex;gap:10px;justify-content:center;padding-top:0">
          <button
            v-for="opt in PREF_OPTS"
            :key="opt.value"
            :class="['cs-btn-outline', prefNudge.saving && 'cs-btn-disabled']"
            :style="prefNudge.choice === opt.value ? 'background:var(--cs-primary-container);border-color:var(--cs-primary);color:var(--cs-primary);font-weight:700' : ''"
            @click="submitPrefNudge(opt.value)"
          >
            {{ opt.emoji }} {{ opt.label }}
          </button>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Skip" @click="prefNudge.show = false" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { groupApi, taskApi, marketplaceApi, messageApi, api } from '../services/api';
import { useAuthStore } from '../stores/auth';
import { useNotificationStore } from '../stores/notifications';
import { NotificationSocketService } from '../services/NotificationSocketService';
import FairnessChart from '../components/charts/FairnessChart.vue';

const route = useRoute();
const router = useRouter();
const groupId = route.params.id as string;
const authStore = useAuthStore();
const notifStore = useNotificationStore();
const myUserId = computed(() => authStore.userId);

// Initialise tab from ?tab= query param so notification deep-links land on the right section.
const VALID_TABS = ['tasks', 'people', 'discover', 'chat', 'settings', 'analytics'] as const;
const initialTab = (VALID_TABS as readonly string[]).includes(route.query.tab as string)
  ? (route.query.tab as string)
  : 'tasks';
const tab = ref(initialTab);
watch(tab, (newTab) => {
  if (newTab === 'chat') loadChatHistory();
  if (newTab === 'analytics') loadAnalytics();
});
// Re-navigate to correct tab when query param changes (e.g. clicking a second notification for same group)
watch(() => route.query.tab, (newTabQuery) => {
  if (route.params.id !== groupId) return;
  const t = newTabQuery as string;
  if ((VALID_TABS as readonly string[]).includes(t) && t !== tab.value) {
    tab.value = t;
  }
});

// Per-tab unread badge counts
const tabBadge = (t: string) => notifStore.tabBadge(groupId, t);
const group = ref<any>(null);
const members = ref<any[]>([]);
const tasks = ref<any[]>([]);
const leaderboard = ref<any[]>([]);
const proposals = ref<any[]>([]);
const templates = ref<any[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Chat
const chatMessages = ref<any[]>([]);
const chatInput = ref('');
const chatBox = ref<HTMLElement | null>(null);
const chatInputEl = ref<HTMLInputElement | null>(null);
const receiptPopoverMsgId = ref<number | null>(null);
const mentionQuery = ref<string | null>(null);
const mentionIndex = ref(0);
const socketSvc = new NotificationSocketService();

// Invite
const invite = ref({ email: '', role: 'member', loading: false, message: '', error: false });

// Leave group
const leaveLoading = ref(false);
const leaveError = ref('');

// Post-completion preference nudge
const PREF_OPTS = [
  { value: 'prefer', label: 'Enjoyed it', emoji: '👍' },
  { value: 'neutral', label: 'Neutral',   emoji: '😐' },
  { value: 'avoid',  label: 'Disliked',   emoji: '👎' },
] as const;
const prefNudge = ref<{
  show: boolean;
  templateId: number | null;
  taskName: string;
  choice: string | null;
  saving: boolean;
}>({ show: false, templateId: null, taskName: '', choice: null, saving: false });

// Analytics
const groupStats = ref<any>(null);
const assignmentMatrix = ref<Record<string, number> | null>(null);
const analyticsLoading = ref(false);
const analyticsError = ref<string | null>(null);

// Task assignment breakdown ("Why assigned?")
const expandedBreakdown = ref<number | null>(null);
const breakdownCache = ref<Record<number, any>>({});
const breakdownLoading = ref<Record<number, boolean>>({});

const memberNameMap = computed(() => {
  const m: Record<string, string> = {};
  members.value.forEach((mem: any) => { m[String(mem.user_id)] = mem.username; });
  return m;
});

const matrixSorted = computed(() => {
  if (!assignmentMatrix.value) return [];
  return Object.entries(assignmentMatrix.value).sort((a, b) => (a[1] as number) - (b[1] as number));
});

// Marketplace
const marketplaceListings = ref<any[]>([]);
const marketplaceLoading = ref(false);
const claimingListing = ref<Record<number, boolean>>({});
const cancellingListing = ref<Record<number, boolean>>({});
const listMarketplaceDialog = ref<{ show: boolean; task: any | null; bonusPoints: number; loading: boolean }>({
  show: false, task: null, bonusPoints: 0, loading: false,
});

// Swap dialog
const swapDialog = ref<{ show: boolean; task: any | null; targetUserId: string | null; reason: string; loading: boolean }>({
  show: false, task: null, targetUserId: null, reason: '', loading: false,
});

// Current user's points from leaderboard
const myPoints = computed(() => {
  const me = leaderboard.value.find(r => String(r.user_id) === String(myUserId.value));
  return me?.total_points ?? 0;
});

// Members the current user can swap with (everyone else, active members)
const swappableMembers = computed(() => [
  { label: 'Anyone in the group (open request)', value: '' },
  ...members.value
    .filter(m => String(m.user_id) !== String(myUserId.value))
    .map(m => ({ label: m.username, value: String(m.user_id) })),
]);

// Photo proof
const proofInputRef = ref<HTMLInputElement | null>(null);
const proofUploading = ref<Record<number, boolean>>({});
let proofTargetTaskId: number | null = null;

function triggerProofUpload(taskId: number) {
  proofTargetTaskId = taskId;
  proofInputRef.value?.click();
}

async function handleProofFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || proofTargetTaskId === null) return;
  const taskId = proofTargetTaskId;
  proofTargetTaskId = null;
  input.value = '';
  proofUploading.value[taskId] = true;
  try {
    const form = new FormData();
    form.append('photo', file);
    const res = await api.post(`/api/tasks/${taskId}/upload-proof/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    const idx = tasks.value.findIndex(t => t.id === taskId);
    if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], photo_proof: res.data.photo_url };
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to upload photo proof.';
  } finally {
    proofUploading.value[taskId] = false;
  }
}

// Proposal / suggestion form
const showProposalForm = ref(false);
const proposalForm = ref({
  name: '', category: 'other', recurring_choice: 'none', recur_value: 3,
  difficulty: 1, estimated_mins: 30, due_datetime: '', reason: '', loading: false,
});

// Per-proposal action state for optimistic loading
const proposalAction = ref<Record<number, 'approving' | 'rejecting' | null>>({});

// Approve dialog
const approveDialog = ref<{
  show: boolean; proposalId: number | null; loading: boolean;
  name: string; category: string; recurring_choice: string; recur_value: number;
  difficulty: number; estimated_mins: number; due_datetime: string; approval_note: string;
}>({
  show: false, proposalId: null, loading: false,
  name: '', category: 'other', recurring_choice: 'none', recur_value: 3,
  difficulty: 1, estimated_mins: 30, due_datetime: '', approval_note: '',
});

// Reject dialog
const rejectDialog = ref<{ show: boolean; proposalId: number | null; note: string; loading: boolean }>({
  show: false, proposalId: null, note: '', loading: false,
});

// Template form
const showTemplateForm = ref(false);
const templateForm = ref({
  name: '', category: 'cleaning', recurring_choice: 'none', importance: 'core',
  difficulty: 3, due_datetime: '', photo_proof_required: false,
  recur_value: 7, days_of_week: [] as string[], loading: false,
});

// Settings
const settings = ref({
  photo_proof_required: false,
  task_proposal_voting_required: false,
  loading: false, message: '', error: false,
});

// Context-aware invite role picker
const inviteRoleLabel = computed(() => {
  const gt = group.value?.group_type;
  if (gt === 'family') return 'Add as';
  if (gt === 'work_team') return 'Role';
  return 'Role';
});

const inviteRoleOptions = computed(() => {
  const gt = group.value?.group_type;
  if (gt === 'family') {
    return [
      { label: 'Child', value: 'member' },
      { label: 'Adult', value: 'moderator' },
    ];
  }
  if (gt === 'work_team') {
    return [
      { label: 'Member', value: 'member' },
      { label: 'Team Lead', value: 'moderator' },
    ];
  }
  return [
    { label: 'Member', value: 'member' },
    { label: 'Moderator', value: 'moderator' },
  ];
});

const recurrenceOptions = [
  { label: 'No repeat', value: 'none' },
  { label: 'Weekly', value: 'weekly' },
  { label: 'Monthly', value: 'monthly' },
  { label: 'Every N days', value: 'every_n_days' },
  { label: 'Custom (days of week)', value: 'custom' },
];

const categoryOptions = [
  { label: 'Cleaning', value: 'cleaning' },
  { label: 'Cooking', value: 'cooking' },
  { label: 'Laundry', value: 'laundry' },
  { label: 'Maintenance', value: 'maintenance' },
  { label: 'Other', value: 'other' },
];

const importanceOptions = [
  { label: 'Core', value: 'core' },
  { label: 'Additional', value: 'additional' },
];

const templateOptions = computed(() =>
  templates.value.map(t => ({ label: t.name, value: t.id }))
);

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    const [gRes, mRes, tRes] = await Promise.all([
      groupApi.get(groupId),
      groupApi.members(groupId),
      taskApi.groupTasks(groupId),
    ]);
    group.value = gRes.data;
    members.value = mRes.data;
    tasks.value = tRes.data;
    settings.value.photo_proof_required = gRes.data.photo_proof_required;
    settings.value.task_proposal_voting_required = gRes.data.task_proposal_voting_required;
    // Set sensible default invite role based on group type
    invite.value.role = gRes.data.group_type === 'flatshare' ? 'moderator' : 'member';
    loadLeaderboard();
    loadProposals();
    loadTemplates();
    loadMarketplace();
    loadChatHistory();
  } catch {
    error.value = 'Failed to load group.';
  } finally {
    loading.value = false;
  }
}

async function loadLeaderboard() {
  try { leaderboard.value = (await groupApi.leaderboard(groupId)).data; } catch (e: any) {
    console.error('loadLeaderboard failed', e);
  }
}
async function loadProposals() {
  try { proposals.value = (await groupApi.proposals(groupId)).data; } catch (e: any) {
    console.error('loadProposals failed', e);
  }
}
async function loadTemplates() {
  try {
    const { api } = await import('../services/api');
    const res = await api.get(`/api/groups/${groupId}/task-templates/`);
    templates.value = res.data;
  } catch (e: any) {
    console.error('loadTemplates failed', e);
  }
}

async function deleteTemplate(templateId: number) {
  try {
    const { api } = await import('../services/api');
    await api.delete(`/api/task-templates/${templateId}/`);
    await loadTemplates();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to delete template.';
  }
}

async function toggleBreakdown(taskId: number) {
  if (expandedBreakdown.value === taskId) {
    expandedBreakdown.value = null;
    return;
  }
  expandedBreakdown.value = taskId;
  if (breakdownCache.value[taskId]) return; // already loaded
  breakdownLoading.value = { ...breakdownLoading.value, [taskId]: true };
  try {
    const res = await api.get(`/api/tasks/${taskId}/assignment-breakdown/`);
    breakdownCache.value = { ...breakdownCache.value, [taskId]: res.data };
  } catch {
    breakdownCache.value = {
      ...breakdownCache.value,
      [taskId]: { breakdown_available: false, candidates: [] },
    };
  } finally {
    breakdownLoading.value = { ...breakdownLoading.value, [taskId]: false };
  }
}

async function loadAnalytics() {
  if (groupStats.value) return; // already loaded
  analyticsLoading.value = true;
  analyticsError.value = null;
  try {
    const [statsRes, matrixRes] = await Promise.allSettled([
      groupApi.stats(groupId),
      groupApi.assignmentMatrix(groupId),
    ]);
    if (statsRes.status === 'fulfilled') groupStats.value = statsRes.value.data;
    if (matrixRes.status === 'fulfilled') assignmentMatrix.value = matrixRes.value.data;
    if (statsRes.status === 'rejected' && matrixRes.status === 'rejected') {
      analyticsError.value = 'Failed to load analytics.';
    }
  } finally {
    analyticsLoading.value = false;
  }
}

async function loadMarketplace() {
  marketplaceLoading.value = true;
  try {
    marketplaceListings.value = (await marketplaceApi.groupListings(groupId)).data;
  } catch (e: any) {
    console.error('loadMarketplace failed', e);
  } finally {
    marketplaceLoading.value = false;
  }
}

async function loadChatHistory() {
  try {
    const res = await messageApi.list(groupId);
    chatMessages.value = res.data;
    nextTick(() => {
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight;
    });
    _markIncomingRead(res.data);
  } catch (e: any) {
    console.error('loadChatHistory failed', e);
  }
}

function _markIncomingRead(msgs: any[]) {
  const unread = msgs
    .filter(m => String(m.sender_id) !== String(myUserId.value))
    .map(m => m.id);
  if (unread.length) {
    // REST for persistence, WS to fan-out the tick update to the sender in real time
    messageApi.markRead(groupId, unread).catch(() => {});
    socketSvc.sendMarkRead(groupId, unread);
  }
}

async function claimListing(listingId: number) {
  claimingListing.value[listingId] = true;
  try {
    await marketplaceApi.claim(listingId);
    await Promise.all([loadMarketplace(), taskApi.groupTasks(groupId).then(r => { tasks.value = r.data; })]);
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to claim task.';
  } finally {
    claimingListing.value[listingId] = false;
  }
}

async function cancelListing(listingId: number) {
  cancellingListing.value[listingId] = true;
  try {
    await marketplaceApi.cancel(listingId);
    await Promise.all([loadMarketplace(), taskApi.groupTasks(groupId).then(r => { tasks.value = r.data; })]);
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to remove listing.';
  } finally {
    cancellingListing.value[listingId] = false;
  }
}

function openSwapDialog(task: any) {
  swapDialog.value = { show: true, task, targetUserId: null, reason: '', loading: false };
}

async function submitSwap() {
  if (!swapDialog.value.task) return;
  swapDialog.value.loading = true;
  try {
    const payload: { to_user_id?: string; reason?: string } = {};
    if (swapDialog.value.targetUserId) payload.to_user_id = swapDialog.value.targetUserId;
    if (swapDialog.value.reason.trim()) payload.reason = swapDialog.value.reason.trim();
    await taskApi.createSwap(swapDialog.value.task.id, payload);
    swapDialog.value.show = false;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to request swap.';
  } finally {
    swapDialog.value.loading = false;
  }
}

function openListMarketplace(task: any) {
  listMarketplaceDialog.value = { show: true, task, bonusPoints: 0, loading: false };
}

async function submitListMarketplace() {
  if (!listMarketplaceDialog.value.task) return;
  listMarketplaceDialog.value.loading = true;
  try {
    await taskApi.listMarketplace(listMarketplaceDialog.value.task.id, {
      bonus_points: listMarketplaceDialog.value.bonusPoints || 0,
    });
    listMarketplaceDialog.value.show = false;
    tasks.value = (await taskApi.groupTasks(groupId)).data;
    await loadMarketplace();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to list task on marketplace.';
  } finally {
    listMarketplaceDialog.value.loading = false;
  }
}

async function completeTask(id: number) {
  try {
    await taskApi.complete(id, true);
    tasks.value = (await taskApi.groupTasks(groupId)).data;
    // Show preference nudge for the completed task
    const completed = tasks.value.find((t: any) => t.id === id)
      ?? (await taskApi.get(id)).data;
    if (completed?.template_id) {
      prefNudge.value = {
        show: true,
        templateId: completed.template_id,
        taskName: completed.template_name ?? 'this task',
        choice: null,
        saving: false,
      };
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to complete task.';
  }
}

async function submitPrefNudge(preference: string) {
  if (!prefNudge.value.templateId || prefNudge.value.saving) return;
  prefNudge.value.choice = preference;
  prefNudge.value.saving = true;
  try {
    const { api } = await import('../services/api');
    await api.put(`/api/task-templates/${prefNudge.value.templateId}/my-preference/`, { preference });
  } catch {
    // Silently ignore — preference is best-effort
  } finally {
    prefNudge.value.saving = false;
    prefNudge.value.show = false;
  }
}

async function uncompleteTask(id: number) {
  try {
    await taskApi.complete(id, false);
    tasks.value = (await taskApi.groupTasks(groupId)).data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to reopen task.';
  }
}

async function inviteMember() {
  invite.value.loading = true;
  invite.value.message = '';
  try {
    await groupApi.invite(groupId, { email: invite.value.email, role: invite.value.role });
    invite.value.message = 'Invitation sent.';
    invite.value.error = false;
    invite.value.email = '';
  } catch (e: any) {
    invite.value.message = e?.response?.data?.detail ?? 'Failed to invite.';
    invite.value.error = true;
  } finally {
    invite.value.loading = false;
  }
}

async function submitProposal() {
  if (!proposalForm.value.name.trim()) { error.value = 'Task name is required.'; return; }
  if (!proposalForm.value.due_datetime) { error.value = 'Please select a start date.'; return; }
  proposalForm.value.loading = true;
  try {
    const { name, category, recurring_choice, recur_value, difficulty, estimated_mins, due_datetime, reason } = proposalForm.value;
    await groupApi.createProposal(groupId, {
      payload: {
        name: name.trim(),
        category,
        recurring_choice,
        recur_value: recurring_choice === 'every_n_days' ? recur_value : undefined,
        difficulty,
        estimated_mins,
        next_due: new Date(due_datetime).toISOString(),
      },
      reason: reason.trim(),
    });
    showProposalForm.value = false;
    proposalForm.value = { name: '', category: 'other', recurring_choice: 'none', recur_value: 3, difficulty: 1, estimated_mins: 30, due_datetime: '', reason: '', loading: false };
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to submit suggestion.';
  } finally {
    proposalForm.value.loading = false;
  }
}

function openApproveDialog(p: any) {
  const pp = p.proposed_payload ?? {};
  const due = pp.next_due ? new Date(pp.next_due).toISOString().slice(0, 16) : '';
  approveDialog.value = {
    show: true, proposalId: p.id, loading: false,
    name: pp.name ?? '', category: pp.category ?? 'other',
    recurring_choice: pp.recurring_choice ?? 'none', recur_value: pp.recur_value ?? 3,
    difficulty: pp.difficulty ?? 1, estimated_mins: pp.estimated_mins ?? 30,
    due_datetime: due, approval_note: '',
  };
}

function openRejectDialog(p: any) {
  rejectDialog.value = { show: true, proposalId: p.id, note: '', loading: false };
}

async function submitApprove() {
  const d = approveDialog.value;
  if (!d.proposalId) return;
  d.loading = true;
  proposalAction.value[d.proposalId] = 'approving';
  try {
    const editedPayload = {
      name: d.name.trim(),
      category: d.category,
      recurring_choice: d.recurring_choice,
      recur_value: d.recurring_choice === 'every_n_days' ? d.recur_value : undefined,
      difficulty: d.difficulty,
      estimated_mins: d.estimated_mins,
      next_due: new Date(d.due_datetime).toISOString(),
    };
    await groupApi.approveProposal(d.proposalId, { edited_payload: editedPayload, approval_note: d.approval_note });
    approveDialog.value.show = false;
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to approve suggestion.';
  } finally {
    d.loading = false;
    if (d.proposalId) delete proposalAction.value[d.proposalId];
  }
}

async function submitReject() {
  const d = rejectDialog.value;
  if (!d.proposalId) return;
  d.loading = true;
  proposalAction.value[d.proposalId] = 'rejecting';
  try {
    await groupApi.rejectProposal(d.proposalId, { note: d.note });
    rejectDialog.value.show = false;
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to decline suggestion.';
  } finally {
    d.loading = false;
    if (d.proposalId) delete proposalAction.value[d.proposalId];
  }
}

async function submitTemplate() {
  if (!templateForm.value.due_datetime) {
    error.value = 'Please select a due date and time.';
    return;
  }
  templateForm.value.loading = true;
  try {
    const { api } = await import('../services/api');
    const { loading: _loading, due_datetime, ...rest } = templateForm.value;
    const next_due = new Date(due_datetime).toISOString();
    const res = await api.post(`/api/groups/${groupId}/task-templates/`, { ...rest, next_due });
    showTemplateForm.value = false;
    templateForm.value = { name: '', category: 'cleaning', recurring_choice: 'none', importance: 'core', difficulty: 3, due_datetime: '', photo_proof_required: false, recur_value: 7, days_of_week: [], loading: false };
    const created = res.data.occurrences_created ?? 0;
    if (created > 0) {
      tasks.value = (await (await import('../services/api')).taskApi.groupTasks(groupId)).data;
    }
    await loadTemplates();
    await loadProposals();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to create task.';
  } finally {
    templateForm.value.loading = false;
  }
}

async function saveSettings() {
  settings.value.loading = true;
  settings.value.message = '';
  try {
    await groupApi.settings(groupId, {
      photo_proof_required: settings.value.photo_proof_required,
      task_proposal_voting_required: settings.value.task_proposal_voting_required,
    });
    settings.value.message = 'Settings saved.';
    settings.value.error = false;
  } catch (e: any) {
    settings.value.message = e?.response?.data?.detail ?? 'Failed to save.';
    settings.value.error = true;
  } finally {
    settings.value.loading = false;
  }
}

async function leaveGroup() {
  if (!window.confirm('Are you sure you want to leave this group?')) return;
  leaveLoading.value = true;
  leaveError.value = '';
  try {
    const { api } = await import('../services/api');
    await api.post(`/api/groups/${groupId}/leave/`);
    router.push({ name: 'groups' });
  } catch (e: any) {
    leaveError.value = e?.response?.data?.detail ?? 'Failed to leave group.';
  } finally {
    leaveLoading.value = false;
  }
}

// @mention autocomplete
const mentionDropdown = computed(() => {
  if (mentionQuery.value === null) return [];
  const q = mentionQuery.value.toLowerCase();
  const items: { value: string; label: string }[] = [];
  // @all always first when query is empty or matches
  if ('all'.startsWith(q)) items.push({ value: 'all', label: 'all  — notify everyone' });
  for (const m of members.value) {
    const uname: string = m.username || '';
    const display: string = m.display_name || m.first_name || uname;
    if (uname.toLowerCase().startsWith(q) || display.toLowerCase().startsWith(q)) {
      items.push({ value: uname, label: `${display} (${uname})` });
    }
  }
  return items.slice(0, 6);
});

function onChatInput() {
  const val = chatInput.value;
  const cursor = chatInputEl.value?.selectionStart ?? val.length;
  // Find the @-word before the cursor
  const before = val.slice(0, cursor);
  const match = before.match(/@(\w*)$/);
  if (match) {
    mentionQuery.value = match[1];
    mentionIndex.value = 0;
  } else {
    mentionQuery.value = null;
  }
}

function onChatKeydown(e: KeyboardEvent) {
  if (!mentionDropdown.value.length) return;
  if (e.key === 'ArrowDown') { e.preventDefault(); mentionIndex.value = (mentionIndex.value + 1) % mentionDropdown.value.length; }
  else if (e.key === 'ArrowUp') { e.preventDefault(); mentionIndex.value = (mentionIndex.value - 1 + mentionDropdown.value.length) % mentionDropdown.value.length; }
  else if (e.key === 'Tab' || e.key === 'Enter') {
    if (mentionDropdown.value.length > 0) {
      e.preventDefault();
      insertMention(mentionDropdown.value[mentionIndex.value].value);
    }
  } else if (e.key === 'Escape') {
    mentionQuery.value = null;
  }
}

function insertMention(username: string) {
  const val = chatInput.value;
  const cursor = chatInputEl.value?.selectionStart ?? val.length;
  const before = val.slice(0, cursor);
  const after = val.slice(cursor);
  const replaced = before.replace(/@(\w*)$/, `@${username} `);
  chatInput.value = replaced + after;
  mentionQuery.value = null;
  nextTick(() => {
    const pos = replaced.length;
    chatInputEl.value?.setSelectionRange(pos, pos);
    chatInputEl.value?.focus();
  });
}

function renderChatBody(body: string): string {
  const escaped = body
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped.replace(/@(\w+)/g, '<span class="cs-mention">@$1</span>');
}

function sendMessage() {
  const body = chatInput.value.trim();
  if (!body) return;
  mentionQuery.value = null;
  socketSvc.sendChatMessage(groupId, body);
  chatInput.value = '';
}

function formatDate(iso: string) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function statusChipClass(status: string) {
  const map: Record<string, string> = {
    pending: 'cs-chip--pending',
    snoozed: 'cs-chip--snoozed',
    overdue: 'cs-chip--overdue',
    completed: 'cs-chip--done',
    suggested: 'cs-chip--pending',
  };
  return map[status] ?? 'cs-chip--snoozed';
}

function proposalChipClass(state: string) {
  const map: Record<string, string> = {
    pending: 'cs-chip--pending',
    approved: 'cs-chip--done',
    rejected: 'cs-chip--overdue',
    expired: 'cs-chip--snoozed',
  };
  return map[state] ?? 'cs-chip--snoozed';
}

onMounted(() => {
  loadAll();
  socketSvc.onChat((msg) => {
    if (msg.group_id === groupId) {
      chatMessages.value.push(msg);
      nextTick(() => {
        if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight;
      });
      // Mark incoming messages as read immediately
      if (String(msg.sender_id) !== String(myUserId.value)) {
        messageApi.markRead(groupId, [msg.id]).catch(() => {});
        socketSvc.sendMarkRead(groupId, [msg.id]);
      }
    }
  });
  socketSvc.onReceiptsUpdate((data: { message_ids: number[]; user_id: string; username: string; seen_at: string }) => {
    if (String(data.user_id) === String(myUserId.value)) return;
    data.message_ids.forEach(mid => {
      const m = chatMessages.value.find(x => x.id === mid);
      if (!m) return;
      if (!m.read_by) m.read_by = [];
      if (!m.read_by.find((r: any) => r.user_id === data.user_id)) {
        m.read_by.push({ user_id: data.user_id, username: data.username, seen_at: data.seen_at });
      }
      // recompute all_read: every non-sender member has read it
      const nonSenderCount = Math.max((members.value?.length ?? 1) - 1, 0);
      m.all_read = nonSenderCount > 0 && m.read_by.length >= nonSenderCount;
    });
  });
  socketSvc.connect();
});
onUnmounted(() => socketSvc.disconnect());
</script>

<style scoped>
.cs-chat-messages {
  height: 320px;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cs-chat-bubble { max-width: 70%; }
.cs-chat-bubble--self { margin-left: auto; }
.cs-chat-bubble--other { margin-right: auto; }
.cs-chat-meta { font-size: 11px; color: var(--cs-muted); margin-bottom: 3px; }
.cs-chat-text {
  background: var(--cs-surface);
  border-radius: 12px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--cs-on-surface);
  display: inline-block;
}
.cs-chat-bubble--self .cs-chat-text {
  background: var(--cs-primary-container);
  color: var(--cs-on-primary-container);
}
.cs-chat-input-row {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--cs-outline-variant);
  align-items: center;
}
.cs-chat-tick-wrap {
  position: relative;
  text-align: right;
  margin-top: 2px;
}
.cs-chat-tick {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  line-height: 1;
}
.cs-chat-tick .material-symbols-outlined {
  font-size: 14px;
  color: var(--cs-muted);
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 16;
}
/* Some (but not all) have read — grey double tick */
.cs-chat-tick--some .material-symbols-outlined {
  color: var(--cs-outline);
  font-variation-settings: 'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 16;
}
/* Everyone has read — green double tick */
.cs-chat-tick--all .material-symbols-outlined {
  color: #22c55e;
  font-variation-settings: 'FILL' 1, 'wght' 600, 'GRAD' 0, 'opsz' 16;
}
/* Reader popover */
.cs-receipt-popover {
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  background: var(--cs-surface-low);
  border: 1px solid var(--cs-outline-variant);
  border-radius: var(--cs-radius-md);
  padding: 10px 12px;
  min-width: 180px;
  max-width: 260px;
  box-shadow: var(--cs-shadow-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 100;
}
.cs-receipt-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

/* @mention highlight in chat bubbles */
.cs-chat-text :deep(.cs-mention) {
  color: var(--cs-primary);
  font-weight: 600;
  background: color-mix(in srgb, var(--cs-primary) 12%, transparent);
  border-radius: 4px;
  padding: 0 3px;
}
.cs-chat-bubble--self .cs-chat-text :deep(.cs-mention) {
  color: var(--cs-on-primary-container);
  background: rgba(255,255,255,0.25);
}

/* @mention autocomplete dropdown */
.cs-mention-dropdown {
  position: relative;
  background: var(--cs-surface-low);
  border: 1px solid var(--cs-outline-variant);
  border-radius: var(--cs-radius-md);
  margin: 0 16px 6px;
  box-shadow: var(--cs-shadow-md);
  overflow: hidden;
}
.cs-mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 13px;
  color: var(--cs-on-surface);
  cursor: pointer;
  text-align: left;
}
.cs-mention-item:hover, .cs-mention-item:focus {
  background: var(--cs-surface-container-high, #eae8e4);
}
.cs-mention-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--cs-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.cs-tab-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--cs-error, #b3261e);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  pointer-events: none;
}
</style>
