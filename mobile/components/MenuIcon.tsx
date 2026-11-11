import { View } from 'react-native';

// Icône « menu » à deux traits de longueurs différentes, comme sur la maquette.
export default function MenuIcon({ color }: { color: string }) {
  return (
    <View style={{ width: 22, gap: 6 }}>
      <View style={{ width: 22, height: 2.5, borderRadius: 2, backgroundColor: color }} />
      <View style={{ width: 14, height: 2.5, borderRadius: 2, backgroundColor: color }} />
    </View>
  );
}