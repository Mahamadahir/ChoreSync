import React, { useCallback } from 'react';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import AppNavigator from './src/navigation/AppNavigator';
import { useAppForegroundRefresh } from './src/hooks/useAppForegroundRefresh';

SplashScreen.preventAutoHideAsync();

export default function App() {
  useAppForegroundRefresh();

  const [fontsLoaded] = useFonts({
    'PlusJakartaSans-Regular':   require('./assets/fonts/PlusJakartaSans-Regular.ttf'),
    'PlusJakartaSans-Medium':    require('./assets/fonts/PlusJakartaSans-Medium.ttf'),
    'PlusJakartaSans-SemiBold':  require('./assets/fonts/PlusJakartaSans-SemiBold.ttf'),
    'PlusJakartaSans-Bold':      require('./assets/fonts/PlusJakartaSans-Bold.ttf'),
    'PlusJakartaSans-ExtraBold': require('./assets/fonts/PlusJakartaSans-ExtraBold.ttf'),
    'BeVietnamPro-Light':        require('./assets/fonts/BeVietnamPro-Light.ttf'),
    'BeVietnamPro-Regular':      require('./assets/fonts/BeVietnamPro-Regular.ttf'),
    'BeVietnamPro-Medium':       require('./assets/fonts/BeVietnamPro-Medium.ttf'),
    'BeVietnamPro-SemiBold':     require('./assets/fonts/BeVietnamPro-SemiBold.ttf'),
    'MaterialSymbols':           require('./assets/fonts/MaterialSymbols.ttf'),
  });

  const onLayoutRootView = useCallback(async () => {
    if (fontsLoaded) await SplashScreen.hideAsync();
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }} onLayout={onLayoutRootView}>
      <AppNavigator />
    </GestureHandlerRootView>
  );
}
