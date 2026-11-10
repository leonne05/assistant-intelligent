import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { KeyboardAvoidingView, View } from 'react-native';
import { IconButton, MD3DarkTheme, PaperProvider, Text, TextInput } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

const theme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#1cb3be',
  },
};

export default function App() {
  const [text, setText] = useState('');
  const [lastMessage, setLastMessage] = useState('');

  function send() {
    if (text.trim() === '') {
      return;
    }
    setLastMessage(text.trim());
    setText('');
  }

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 }}>
              <Text variant="displayMedium" style={{ color: theme.colors.primary }}>
                JARVIS
              </Text>
              <Text variant="titleMedium">
                {lastMessage === '' ? 'Bonjour, que puis-je faire pour toi ?' : `Tu as écrit : ${lastMessage}`}
              </Text>
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 8 }}>
              <TextInput
                mode="outlined"
                placeholder="Écris à Jarvis…"
                value={text}
                onChangeText={setText}
                onSubmitEditing={send}
                style={{ flex: 1 }}
              />
              <IconButton
                icon={text === '' ? 'microphone' : 'send'}
                mode="contained"
                size={28}
                onPress={send}
              />
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
        <StatusBar style="light" />
      </PaperProvider>
    </SafeAreaProvider>
  );
}