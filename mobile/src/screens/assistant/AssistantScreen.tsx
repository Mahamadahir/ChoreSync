import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  FlatList,
  Modal,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Animated,
  ActivityIndicator,
  Pressable,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { chatbotService } from '../../services/chatbotService';
import { api } from '../../services/api';
import * as SecureStore from 'expo-secure-store';
import { Colors, Spacing, Radii, Shadows } from '../../theme';
import AppHeader from '../../components/common/AppHeader';

// ─── Types ────────────────────────────────────────────────────────────────────

type Role = 'user' | 'assistant';

interface ActionChip {
  label: string;
  icon: string;
  value: string;
}

interface Message {
  id: string;
  role: Role;
  content: string;
  chips?: ActionChip[];
  timestamp: Date;
}

const SESSION_KEY = 'choresync_chatbot_session';

// ─── Typing dot (bouncing animation) ─────────────────────────────────────────

function TypingDot({ delay }: { delay: number }) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(anim, { toValue: -6, duration: 300, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0,  duration: 300, useNativeDriver: true }),
        Animated.delay(600 - delay),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, []);

  return <Animated.View style={[styles.typingDot, { transform: [{ translateY: anim }] }]} />;
}

function TypingIndicator() {
  return (
    <View style={styles.typingRow}>
      <View style={styles.botAvatar}>
        <Text style={styles.materialIcon}>smart_toy</Text>
      </View>
      <View style={styles.typingBubble}>
        <TypingDot delay={0} />
        <TypingDot delay={200} />
        <TypingDot delay={400} />
      </View>
    </View>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ message, onChipPress }: {
  message: Message;
  onChipPress: (value: string) => void;
}) {
  if (message.role === 'user') {
    return (
      <View style={styles.userRow}>
        <LinearGradient
          colors={[Colors.terracotta, Colors.brandPrimary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.bubble, styles.userBubble]}
        >
          <Text style={styles.userText}>{message.content}</Text>
        </LinearGradient>
      </View>
    );
  }

  return (
    <View style={styles.botRow}>
      <View style={styles.botAvatar}>
        <Text style={styles.materialIcon}>smart_toy</Text>
      </View>
      <View style={styles.botMessageGroup}>
        <View style={[styles.bubble, styles.botBubble]}>
          <Text style={styles.botText}>{message.content}</Text>
        </View>
        {message.chips && message.chips.length > 0 && (
          <View style={styles.chipsRow}>
            {message.chips.map((chip) => (
              <Pressable
                key={chip.value}
                style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
                onPress={() => onChipPress(chip.value)}
              >
                <Text style={styles.chipMaterialIcon}>{chip.icon}</Text>
                <Text style={styles.chipLabel}>{chip.label}</Text>
              </Pressable>
            ))}
          </View>
        )}
      </View>
    </View>
  );
}

// ─── Date separator ───────────────────────────────────────────────────────────

function DateSeparator() {
  return (
    <View style={styles.dateSeparator}>
      <Text style={styles.dateSeparatorText}>Today</Text>
    </View>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function AssistantScreen() {
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollView>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // History panel
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sessions, setSessions] = useState<{ id: string; preview: string; last_active: string; message_count: number }[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  // Measured height of AppHeader + subBar — used as KAV keyboardVerticalOffset on iOS
  const [headerAreaHeight, setHeaderAreaHeight] = useState(104);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const res = await api.get('/api/assistant/sessions/');
      setSessions(Array.isArray(res.data) ? res.data : []);
    } catch {
      setHistoryError('Could not load session history. Pull to retry.');
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const openHistory = useCallback(() => {
    loadHistory();
    setHistoryOpen(true);
  }, [loadHistory]);

  const loadSession = useCallback(async (id: string) => {
    setHistoryOpen(false);
    setSessionId(id);
    await SecureStore.setItemAsync(SESSION_KEY, id);
    setMessages([]);
    try {
      const { data } = await chatbotService.loadSession(id);
      const history: Message[] = (data.messages ?? []).map(
        (m: { role: string; content: string }, idx: number) => ({
          id: `hist-${idx}`,
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: new Date(),
        }),
      );
      setMessages(history);
    } catch {
      // Non-critical: session still active, user can continue from here
    }
  }, []);

  useEffect(() => {
    SecureStore.getItemAsync(SESSION_KEY).then((id) => {
      if (id) setSessionId(id);
    });
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, isTyping]);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isTyping) return;

    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), role: 'user', content: trimmed, timestamp: new Date() },
    ]);
    setInput('');
    setIsTyping(true);

    try {
      const { data } = await chatbotService.send(trimmed, sessionId);

      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
        SecureStore.setItemAsync(SESSION_KEY, data.session_id);
      }

      const chips: ActionChip[] = Array.isArray(data.options)
        ? data.options.map((opt: string) => ({
            label: opt,
            icon: resolveChipIcon(opt),
            value: opt,
          }))
        : [];

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.reply ?? 'Done!',
          chips,
          timestamp: new Date(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: "Sorry, I couldn't connect right now. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  }, [sessionId, isTyping]);

  const handleClear = useCallback(async () => {
    if (sessionId) {
      await chatbotService.clearSession(sessionId).catch(() => {});
      await SecureStore.deleteItemAsync(SESSION_KEY);
    }
    setMessages([]);
    setSessionId(null);
  }, [sessionId]);

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>

      {/* Measure the fixed header area so KAV can offset correctly on iOS */}
      <View onLayout={e => setHeaderAreaHeight(e.nativeEvent.layout.height)}>
        <AppHeader />

        {/* ── Sub-bar: history + clear ── */}
        <View style={styles.subBar}>
          <TouchableOpacity style={styles.subBarBtn} onPress={openHistory}>
            <Text style={[styles.materialIcon, { color: Colors.stone500, fontSize: 20 }]}>history</Text>
            <Text style={styles.subBarLabel}>History</Text>
          </TouchableOpacity>
          <View style={styles.subBarDivider} />
          <TouchableOpacity style={styles.subBarBtn} onPress={handleClear}>
            <Text style={[styles.materialIcon, { color: Colors.stone500, fontSize: 20 }]}>delete_sweep</Text>
            <Text style={styles.subBarLabel}>Clear chat</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── History modal ── */}
      <Modal
        visible={historyOpen}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setHistoryOpen(false)}
      >
        <View style={styles.historyRoot}>
          <View style={styles.historyHeader}>
            <Text style={styles.historyTitle}>Chat History</Text>
            <TouchableOpacity onPress={() => setHistoryOpen(false)} style={styles.historyCloseBtn}>
              <Text style={[styles.materialIcon, { color: Colors.stone500 }]}>close</Text>
            </TouchableOpacity>
          </View>
          {loadingHistory ? (
            <ActivityIndicator style={{ marginTop: 48 }} color={Colors.brandPrimary} size="large" />
          ) : historyError ? (
            <View style={styles.historyEmpty}>
              <Text style={[styles.materialIcon, { color: Colors.stone300, fontSize: 48 }]}>error_outline</Text>
              <Text style={styles.historyEmptyText}>{historyError}</Text>
              <TouchableOpacity onPress={loadHistory} style={{ marginTop: 12 }}>
                <Text style={{ color: Colors.brandPrimary, fontFamily: 'PlusJakartaSans-SemiBold' }}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : sessions.length === 0 ? (
            <View style={styles.historyEmpty}>
              <Text style={[styles.materialIcon, { color: Colors.stone300, fontSize: 48 }]}>chat_bubble_outline</Text>
              <Text style={styles.historyEmptyText}>No previous sessions</Text>
            </View>
          ) : (
            <FlatList
              data={sessions}
              keyExtractor={(s) => s.id}
              contentContainerStyle={styles.historyList}
              renderItem={({ item }) => (
                <TouchableOpacity
                  activeOpacity={0.75}
                  style={styles.historyItem}
                  onPress={() => loadSession(item.id)}
                >
                  <View style={styles.historyItemIcon}>
                    <Text style={[styles.materialIcon, { color: Colors.brandPrimary, fontSize: 20 }]}>smart_toy</Text>
                  </View>
                  <View style={styles.historyItemBody}>
                    <Text style={styles.historyItemPreview} numberOfLines={2}>
                      {item.preview || 'Empty session'}
                    </Text>
                    <Text style={styles.historyItemMeta}>
                      {item.message_count} messages · {new Date(item.last_active).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </Text>
                  </View>
                  <Text style={[styles.materialIcon, { color: Colors.stone400, fontSize: 18 }]}>chevron_right</Text>
                </TouchableOpacity>
              )}
            />
          )}
        </View>
      </Modal>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? headerAreaHeight + insets.top : 0}
      >
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1 }}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* ── Assistant header ── */}
          <View style={styles.statusHeader}>
            <View style={styles.assistantAvatar}>
              <Text style={[styles.materialIcon, styles.assistantAvatarIcon]}>smart_toy</Text>
            </View>
            <Text style={styles.assistantTitle}>AI Assistant</Text>
            <View style={styles.statusRow}>
              <View style={styles.pulseDot} />
              <Text style={styles.statusLabel}>Always here to help</Text>
            </View>
          </View>

          {/* ── Timeline ── */}
          <View style={styles.timeline}>
            <DateSeparator />
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} onChipPress={send} />
            ))}
            {isTyping && <TypingIndicator />}
          </View>

        </ScrollView>

        {/* ── Input bar (normal flex child — KAV lifts it above the keyboard) ── */}
        <View style={[styles.inputContainer, { paddingBottom: insets.bottom + 8 }]}>
          <View style={styles.inputBar}>
            <TouchableOpacity style={styles.attachBtn}>
              <Text style={[styles.materialIcon, styles.attachIcon]}>attach_file</Text>
            </TouchableOpacity>
            <TextInput
              style={styles.textInput}
              placeholder="Ask the assistant anything..."
              placeholderTextColor={Colors.stone400}
              value={input}
              onChangeText={setInput}
              onSubmitEditing={() => send(input)}
              returnKeyType="send"
              multiline
              scrollEnabled
              textAlignVertical="top"
            />
            <TouchableOpacity onPress={() => send(input)} disabled={!input.trim() || isTyping}>
              <LinearGradient
                colors={[Colors.terracotta, Colors.brandPrimary]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.sendBtn}
              >
                {isTyping
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <Text style={[styles.materialIcon, styles.sendIcon]}>send</Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

// ─── Chip icon resolver ───────────────────────────────────────────────────────

function resolveChipIcon(label: string): string {
  const l = label.toLowerCase();
  if (l === 'none' || l === 'cancel' || l === 'nevermind') return 'cancel';
  if (l.includes('emergency'))            return 'emergency';
  if (l.includes('marketplace') || l.includes('market')) return 'storefront';
  if (l.includes('swap'))                 return 'swap_horiz';
  if (l.includes('view') || l.includes('show')) return 'visibility';
  if (l.includes('accept'))               return 'check_circle';
  if (l.includes('decline'))              return 'cancel';
  // Group name chips (group picker context) — apartment icon
  return 'apartment';
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.warmCream,
  },

  // Material Symbols base (font must be loaded in App.tsx)
  materialIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 24,
  },

  // Sub-bar
  subBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.warmCream,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(168,162,158,0.3)',
    paddingHorizontal: Spacing.lg,
    paddingVertical: 8,
    gap: 0,
  },
  subBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: Radii.full,
  },
  subBarLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 12,
    color: Colors.stone500,
  },
  subBarDivider: {
    width: 1,
    height: 18,
    backgroundColor: 'rgba(168,162,158,0.35)',
    marginHorizontal: 4,
  },

  // History modal
  historyRoot: {
    flex: 1,
    backgroundColor: Colors.warmCream,
  },
  historyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(168,162,158,0.3)',
  },
  historyTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 20,
    color: Colors.charcoal,
  },
  historyCloseBtn: {
    padding: 4,
  },
  historyEmpty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  historyEmptyText: {
    fontFamily: 'PlusJakartaSans-Medium',
    fontSize: 14,
    color: Colors.stone400,
  },
  historyList: {
    padding: 20,
    gap: 10,
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: Colors.white,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(168,162,158,0.2)',
  },
  historyItemIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.lightClay,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  historyItemBody: {
    flex: 1,
    gap: 3,
  },
  historyItemPreview: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 13,
    color: Colors.charcoal,
    lineHeight: 18,
  },
  historyItemMeta: {
    fontFamily: 'PlusJakartaSans-Regular',
    fontSize: 11,
    color: Colors.stone400,
  },

  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
  },

  // Assistant status header
  statusHeader: {
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  assistantAvatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.lightClay,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(168,162,158,0.2)',
  },
  assistantAvatarIcon: {
    fontSize: 36,
    color: Colors.terracotta,
  },
  assistantTitle: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 22,
    color: Colors.charcoal,
    letterSpacing: -0.3,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
  },
  pulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.terracotta,
  },
  statusLabel: {
    fontFamily: 'PlusJakartaSans-SemiBold',
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    color: Colors.stone500,
  },

  // Timeline
  timeline: {
    gap: Spacing.lg,
  },

  // Date separator
  dateSeparator: {
    alignItems: 'center',
    marginVertical: Spacing.xs,
  },
  dateSeparatorText: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 2,
    textTransform: 'uppercase',
    color: Colors.stone400,
  },

  // User bubble
  userRow: {
    alignItems: 'flex-end',
    marginLeft: 48,
  },
  bubble: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  userBubble: {
    borderRadius: Radii['3xl'],
    borderTopRightRadius: 4,
    ...Shadows.editorial,
  },
  userText: {
    fontFamily: 'BeVietnamPro-Regular',
    fontSize: 14,
    lineHeight: 21,
    color: '#FFFFFF',
  },

  // Bot bubble
  botRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginRight: 48,
  },
  botAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.lightClay,
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
    borderWidth: 1,
    borderColor: 'rgba(168,162,158,0.3)',
  },
  botMessageGroup: {
    flex: 1,
    gap: 10,
  },
  botBubble: {
    backgroundColor: Colors.lightClay,
    borderRadius: Radii['3xl'],
    borderTopLeftRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(168,162,158,0.3)',
  },
  botText: {
    fontFamily: 'BeVietnamPro-Regular',
    fontSize: 14,
    lineHeight: 21,
    color: Colors.charcoal,
  },

  // Action chips
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.white,
    borderWidth: 1,
    borderColor: Colors.stone200,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    borderRadius: Radii['2xl'],
    ...Shadows.editorial,
  },
  chipPressed: {
    backgroundColor: Colors.lightClay,
    transform: [{ scale: 0.96 }],
  },
  chipMaterialIcon: {
    fontFamily: 'MaterialSymbols',
    fontSize: 16,
    color: Colors.terracotta,
  },
  chipLabel: {
    fontFamily: 'PlusJakartaSans-Bold',
    fontSize: 10,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: Colors.charcoal,
  },

  // Typing indicator
  typingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginLeft: 50,
  },
  typingBubble: {
    flexDirection: 'row',
    gap: 4,
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: Colors.lightClay,
    borderRadius: 20,
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.stone300,
  },

  // Input bar
  inputContainer: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    backgroundColor: Colors.warmCream,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(168,162,158,0.25)',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: Colors.white,
    borderRadius: Radii['3xl'],
    paddingHorizontal: 10,
    paddingVertical: 10,
    gap: 8,
    borderWidth: 1,
    borderColor: 'rgba(168,162,158,0.3)',
    ...Shadows.editorial,
  },
  attachBtn: {
    padding: 8,
    paddingBottom: Platform.OS === 'ios' ? 10 : 8,
  },
  attachIcon: {
    color: Colors.stone400,
  },
  textInput: {
    flex: 1,
    fontFamily: 'BeVietnamPro-Regular',
    fontSize: 14,
    color: Colors.charcoal,
    paddingVertical: Platform.OS === 'ios' ? 8 : 6,
    minHeight: 40,
    maxHeight: 120,
    lineHeight: 20,
  },
  sendBtn: {
    width: 48,
    height: 48,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendIcon: {
    fontSize: 20,
    color: '#FFFFFF',
  },
});
