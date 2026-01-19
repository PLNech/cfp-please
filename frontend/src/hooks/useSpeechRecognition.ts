/**
 * useSpeechRecognition - Web Speech API wrapper
 *
 * Provides voice input with graceful fallbacks.
 * Uses native browser SpeechRecognition API.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Type definitions for Web Speech API
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  onspeechend: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  }
}

export interface UseSpeechRecognitionOptions {
  /** Language for recognition (default: 'en-US') */
  lang?: string;
  /** Auto-stop after speech ends (default: true) */
  autoStop?: boolean;
  /** Callback when final transcript is ready */
  onResult?: (transcript: string) => void;
  /** Callback on error */
  onError?: (error: string) => void;
}

export interface UseSpeechRecognitionReturn {
  /** Whether browser supports speech recognition */
  isSupported: boolean;
  /** Whether currently listening */
  isListening: boolean;
  /** Current transcript (interim + final) */
  transcript: string;
  /** Final transcript only */
  finalTranscript: string;
  /** Start listening */
  startListening: () => void;
  /** Stop listening */
  stopListening: () => void;
  /** Toggle listening state */
  toggleListening: () => void;
  /** Clear transcript */
  clearTranscript: () => void;
  /** Error message if any */
  error: string | null;
}

// Get SpeechRecognition constructor (with vendor prefix fallback)
const getSpeechRecognition = (): (new () => SpeechRecognitionInstance) | null => {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
};

export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionReturn {
  const {
    lang = 'en-US',
    autoStop = true,
    onResult,
    onError,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const SpeechRecognitionClass = getSpeechRecognition();
  const isSupported = SpeechRecognitionClass !== null;

  // Initialize recognition instance
  useEffect(() => {
    if (!SpeechRecognitionClass) return;

    const recognition = new SpeechRecognitionClass();
    recognition.continuous = !autoStop;
    recognition.interimResults = true;
    recognition.lang = lang;

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      // Update transcripts
      if (final) {
        setFinalTranscript(prev => prev + final);
        setTranscript(prev => prev + final);
        onResult?.(final);
      } else {
        setTranscript(finalTranscript + interim);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      let errorMessage = 'Speech recognition error';

      switch (event.error) {
        case 'no-speech':
          errorMessage = 'No speech detected. Try again.';
          break;
        case 'audio-capture':
          errorMessage = 'No microphone found. Check your device.';
          break;
        case 'not-allowed':
          errorMessage = 'Microphone access denied. Check browser permissions.';
          break;
        case 'network':
          errorMessage = 'Network error. Check your connection.';
          break;
        case 'aborted':
          // User aborted, not an error
          return;
        default:
          errorMessage = `Error: ${event.error}`;
      }

      setError(errorMessage);
      setIsListening(false);
      onError?.(errorMessage);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onspeechend = () => {
      if (autoStop) {
        recognition.stop();
      }
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [SpeechRecognitionClass, lang, autoStop, onResult, onError, finalTranscript]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current || isListening) return;

    setTranscript('');
    setFinalTranscript('');
    setError(null);

    try {
      recognitionRef.current.start();
    } catch (err) {
      // Already started - ignore
      if (err instanceof Error && err.message.includes('already started')) {
        return;
      }
      setError('Failed to start speech recognition');
    }
  }, [isListening]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current || !isListening) return;

    try {
      recognitionRef.current.stop();
    } catch {
      // Already stopped - ignore
    }
  }, [isListening]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const clearTranscript = useCallback(() => {
    setTranscript('');
    setFinalTranscript('');
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    finalTranscript,
    startListening,
    stopListening,
    toggleListening,
    clearTranscript,
    error,
  };
}
