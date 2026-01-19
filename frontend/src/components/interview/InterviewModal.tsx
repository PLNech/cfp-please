/**
 * InterviewModal - AI-powered profile builder conversation
 *
 * Chat-like UI that interviews the user to build a rich profile.
 * Supports voice input via Web Speech API with graceful fallback.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useInterview, type InterviewMessage } from '../../hooks/useInterview';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import type { InterviewProfile } from '../../types';
import './InterviewModal.css';

interface InterviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (profile: InterviewProfile) => void;
  existingProfile?: InterviewProfile;
}

export function InterviewModal({ isOpen, onClose, onComplete, existingProfile: _existingProfile }: InterviewModalProps) {
  const {
    messages,
    suggestions,
    isLoading,
    isComplete,
    profile,
    error: interviewError,
    startInterview,
    sendResponse,
    resetInterview,
  } = useInterview();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Voice input handling
  const handleVoiceResult = useCallback((transcript: string) => {
    // Update input field with final transcript
    setInput(prev => (prev + ' ' + transcript).trim());
  }, []);

  const {
    isSupported: voiceSupported,
    isListening,
    transcript: interimTranscript,
    toggleListening,
    clearTranscript,
    error: voiceError,
  } = useSpeechRecognition({
    lang: 'en-US',
    autoStop: true,
    onResult: handleVoiceResult,
  });

  // Start interview when modal opens
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      startInterview();
    }
  }, [isOpen, messages.length, startInterview]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when not listening
  useEffect(() => {
    if (isOpen && !isLoading && !isListening) {
      inputRef.current?.focus();
    }
  }, [isOpen, isLoading, isListening, messages.length]);

  // Clear voice transcript when input is cleared
  useEffect(() => {
    if (!input) {
      clearTranscript();
    }
  }, [input, clearTranscript]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    sendResponse(text);
    setInput('');
    clearTranscript();
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (isLoading) return;

    if (isComplete) {
      // Handle post-interview actions
      onComplete(profile!);
      onClose();
      return;
    }

    sendResponse(suggestion);
  };

  const handleClose = () => {
    if (isComplete && profile) {
      onComplete(profile);
    }
    onClose();
    // Reset after a delay so animation completes
    setTimeout(resetInterview, 300);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  const handleMicClick = () => {
    if (isLoading) return;
    toggleListening();
  };

  // Display text: show interim transcript while listening, otherwise show input
  const displayText = isListening && interimTranscript
    ? (input + ' ' + interimTranscript).trim()
    : input;

  if (!isOpen) return null;

  return (
    <div className="interview-modal-overlay" onClick={handleBackdropClick}>
      <div className="interview-modal">
        {/* Header */}
        <header className="interview-modal-header">
          <div className="interview-modal-header-content">
            <span className="interview-modal-icon">🎤</span>
            <div>
              <h2 className="interview-modal-title">Profile Interview</h2>
              <p className="interview-modal-subtitle">
                {isComplete ? 'All done!' : "Let's find your perfect CFPs"}
              </p>
            </div>
          </div>
          <button className="interview-modal-close" onClick={handleClose} aria-label="Close">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        {/* Error display */}
        {(interviewError || voiceError) && (
          <div className="interview-error">
            {interviewError || voiceError}
          </div>
        )}

        {/* Messages */}
        <div className="interview-modal-messages">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {isLoading && (
            <div className="interview-message assistant">
              <div className="interview-bubble typing">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions */}
        {suggestions.length > 0 && !isLoading && (
          <div className="interview-suggestions">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                className="interview-suggestion"
                onClick={() => handleSuggestionClick(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        {!isComplete && (
          <form className="interview-modal-input" onSubmit={handleSubmit}>
            {/* Voice input button */}
            {voiceSupported && (
              <button
                type="button"
                className={`interview-mic-btn ${isListening ? 'listening' : ''}`}
                onClick={handleMicClick}
                disabled={isLoading}
                aria-label={isListening ? 'Stop listening' : 'Start voice input'}
              >
                {isListening ? (
                  // Stop icon (square)
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                ) : (
                  // Mic icon
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                )}
              </button>
            )}

            <input
              ref={inputRef}
              type="text"
              value={displayText}
              onChange={(e) => setInput(e.target.value)}
              placeholder={isListening ? 'Listening...' : 'Type or tap mic to speak...'}
              disabled={isLoading}
              className={isListening ? 'listening' : ''}
            />

            <button
              type="submit"
              disabled={!displayText.trim() || isLoading}
              aria-label="Send message"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        )}

        {/* Listening indicator */}
        {isListening && (
          <div className="interview-listening-indicator">
            <span className="listening-pulse" />
            <span>Listening... tap mic to stop</span>
          </div>
        )}

        {/* Complete state */}
        {isComplete && (
          <div className="interview-modal-complete">
            <button className="interview-complete-btn" onClick={handleClose}>
              Start Finding CFPs
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: InterviewMessage }) {
  return (
    <div className={`interview-message ${message.role}`}>
      <div className="interview-bubble">
        {message.content}
      </div>
    </div>
  );
}
