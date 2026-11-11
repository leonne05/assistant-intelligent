import { View } from 'react-native';
import { Text, useTheme } from 'react-native-paper';

export type Message = {
  id: string;
  role: 'user' | 'jarvis';
  text: string;
};

export default function MessageBubble({ message }: { message: Message }) {
  const theme = useTheme();
  const isUser = message.role === 'user';

  return (
    <View
      style={{
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '80%',
        backgroundColor: isUser ? theme.colors.primary : 'rgba(255, 255, 255, 0.08)',
        borderRadius: 20,
        paddingVertical: 10,
        paddingHorizontal: 14,
        marginVertical: 4,
      }}
    >
      <Text variant="bodyLarge" style={{ color: isUser ? '#FFFFFF' : '#E8E6F3' }}>
        {message.text}
      </Text>
    </View>
  );
}