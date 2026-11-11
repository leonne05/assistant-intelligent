import { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Modal, View } from 'react-native';
import { ActivityIndicator, IconButton, Text, TextInput, useTheme } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import JarvisBackground from './JarvisBackground';
import MessageBubble, { Message } from './MessageBubble';

type Props = {
  visible: boolean;
  messages: Message[];
  isThinking: boolean;
  onClose: () => void;
  onSend: (text: string) => void;
};

// La conversation écrite, ouverte avec le bouton menu.
export default function ChatSheet({ visible, messages, isThinking, onClose, onSend }: Props) {
  const theme = useTheme();
  const [text, setText] = useState('');
  const listRef = useRef<FlatList<Message>>(null);

  function send() {
    const content = text.trim();
    if (content === '' || isThinking) {
      return;
    }
    onSend(content);
    setText('');
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <JarvisBackground />
          <SafeAreaView style={{ flex: 1 }}>
            <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
              <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12 }}>
                <IconButton icon="chevron-down" mode="contained" containerColor="#151821" iconColor="#FFFFFF" onPress={onClose} />
                <Text variant="titleMedium" style={{ marginLeft: 8, color: '#E8E6F3' }}>
                  Conversation
                </Text>
              </View>

              {messages.length === 0 ? (
                <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
                  <Text variant="bodyLarge" style={{ color: '#A9A6C2', textAlign: 'center' }}>
                    Vos échanges avec JARVIS, écrits ou parlés, apparaîtront ici.
                  </Text>
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
                  <Text variant="bodyMedium" style={{ marginLeft: 8, color: '#A9A6C2' }}>
                    Je réfléchis…
                  </Text>
                </View>
              )}

              <View style={{ flexDirection: 'row', alignItems: 'center', padding: 8 }}>
                <TextInput
                  mode="outlined"
                  placeholder="Écrire à JARVIS…"
                  value={text}
                  onChangeText={setText}
                  onSubmitEditing={send}
                  style={{ flex: 1, backgroundColor: '#151821' }}
                  outlineStyle={{ borderRadius: 24 }}
                />
                <IconButton
                  icon="arrow-up"
                  mode="contained"
                  containerColor={theme.colors.primary}
                  iconColor="#FFFFFF"
                  size={26}
                  disabled={isThinking || text.trim() === ''}
                  onPress={send}
                />
              </View>
            </KeyboardAvoidingView>
          </SafeAreaView>
        </View>
      </SafeAreaProvider>
    </Modal>
  );
}