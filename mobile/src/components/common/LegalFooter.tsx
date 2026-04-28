import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Linking } from 'react-native';
import { Palette as C } from '../../theme';

const PRIVACY_URL = 'https://choresync-app.mahamadahir.com/privacy';
const TERMS_URL   = 'https://choresync-app.mahamadahir.com/terms';

export default function LegalFooter() {
  return (
    <View style={s.ribbon}>
      <TouchableOpacity onPress={() => Linking.openURL(PRIVACY_URL)}>
        <Text style={s.link}>Privacy Policy</Text>
      </TouchableOpacity>
      <Text style={s.dot}>·</Text>
      <TouchableOpacity onPress={() => Linking.openURL(TERMS_URL)}>
        <Text style={s.link}>Terms of Service</Text>
      </TouchableOpacity>
    </View>
  );
}

const s = StyleSheet.create({
  ribbon: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(218,193,189,0.4)',
    backgroundColor: C.bg,
  },
  link: {
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 12,
    color: C.onSurfaceVariant,
    opacity: 0.75,
  },
  dot: {
    fontSize: 12,
    color: C.onSurfaceVariant,
    opacity: 0.4,
  },
});
