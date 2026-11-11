import { Canvas, Fill, LinearGradient, Rect, RadialGradient, vec } from '@shopify/react-native-skia';
import { StyleSheet, useWindowDimensions } from 'react-native';

// Fond sombre : mauve en haut à gauche, gris-bleu en haut à droite, presque noir en bas.
export default function JarvisBackground() {
  const { width, height } = useWindowDimensions();

  return (
    <Canvas style={StyleSheet.absoluteFill} pointerEvents="none">
      <Fill>
        <LinearGradient start={vec(0, 0)} end={vec(0, height * 0.6)} colors={['#1B1A24', '#0A0C12']} />
      </Fill>
      <Rect x={0} y={0} width={width} height={height}>
        <RadialGradient
          c={vec(width * 0.1, 0)}
          r={width * 0.9}
          colors={['rgba(110, 70, 100, 0.75)', 'rgba(110, 70, 100, 0)']}
        />
      </Rect>
      <Rect x={0} y={0} width={width} height={height}>
        <RadialGradient
          c={vec(width * 0.95, height * 0.05)}
          r={width * 0.85}
          colors={['rgba(75, 92, 118, 0.7)', 'rgba(75, 92, 118, 0)']}
        />
      </Rect>
      <Rect x={0} y={0} width={width} height={height}>
        <RadialGradient
          c={vec(width / 2, height * 0.5)}
          r={width * 0.7}
          colors={['rgba(60, 40, 120, 0.35)', 'rgba(60, 40, 120, 0)']}
        />
      </Rect>
    </Canvas>
  );
}