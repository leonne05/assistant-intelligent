import { StatusBar } from 'expo-status-bar';
import { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, View } from 'react-native';
import { ActivityIndicator, IconButton, MD3LightTheme, PaperProvider, Text, TextInput } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import MessageBubble, { Message } from './components/MessageBubble';

// Adresse du serveur Python : remplace par l'adresse IPv4 de ton PC (commande ipconfig).
const API_URL = 'http://172.20.10.7:8000';

const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#E0479E',
    background: '#FFFFFF',
  },
};

export default function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);

  function addMessage(role: Message['role'], content: string) {
    const message: Message = { id: Date.now().toString() + role, role, text: content };
    setMessages((previous) => [...previous, message]);
  }

  async function askJarvis(content: string) {
    setIsThinking(true);
    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
      });
      const data = await response.json();

      if (!response.ok) {
        addMessage('jarvis', data.detail ?? 'Une erreur est survenue, réessaie.');
        return;
      }
      addMessage('jarvis', data.reply);
    } catch {
      addMessage('jarvis', "Je n'arrive pas à joindre mon cerveau. Vérifie que le serveur est lancé et que tu es sur le même Wi-Fi.");
    } finally {
      setIsThinking(false);
    }
  }

  function send() {
    const content = text.trim();
    if (content === '' || isThinking) {
      return;
    }
    addMessage('user', content);
    setText('');
    askJarvis(content);
  }

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
            {messages.length === 0 ? (
              <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                <Text variant="displayMedium" style={{ color: theme.colors.primary }}>
                  JARVIS
                </Text>
                <Text variant="titleMedium">Bonjour, que puis-je faire pour toi ?</Text>
              </View>
            ) : (
              <FlatList
                ref={listRef}
                data={messages}
                keyExtractor={(message) => message.id}
                renderItem={({ item }) => <MessageBubble message={item} />}
                contentContainerStyle={{ padding: 12 }}
                onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
              />
            )}

            {isThinking && (
              <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16 }}>
                <ActivityIndicator size="small" />
                <Text variant="bodyMedium" style={{ marginLeft: 8 }}>
                  JARVIS réfléchit…
                </Text>
              </View>
            )}

            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 8 }}>
              <TextInput
                mode="outlined"
                placeholder="Écris à JARVIS…"
                value={text}
                onChangeText={setText}
                onSubmitEditing={send}
                style={{ flex: 1 }}
              />
              <IconButton
                icon={text === '' ? 'microphone' : 'send'}
                mode="contained"
                containerColor={theme.colors.primary}
                iconColor="#FFFFFF"
                size={28}
                disabled={isThinking}
                onPress={send}
              />
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
        <StatusBar style="dark" />
      </PaperProvider>
    </SafeAreaProvider>
  );
}