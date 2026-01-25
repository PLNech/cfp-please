/**
 * useProfile - Manage user preferences in localStorage
 *
 * No auth required - just pick interests and go.
 */

import { useState, useCallback, useEffect } from 'react';
import type { UserProfile } from '../types';
import { DEFAULT_PROFILE } from '../types';

const STORAGE_KEY = 'cfp-profile';
const MAX_TOPICS = 5;
const MAX_VIEWED = 20;
const MAX_SAVED = 50;
const MAX_WATCHED_TALKS = 50;
const MAX_FAVORITE_TALKS = 50;
const MAX_FAVORITE_SPEAKERS = 20;

function loadProfile(): UserProfile {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return { ...DEFAULT_PROFILE, ...parsed };
    }
  } catch (e) {
    console.warn('Failed to load profile from localStorage:', e);
  }
  return { ...DEFAULT_PROFILE };
}

function saveProfile(profile: UserProfile): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch (e) {
    console.warn('Failed to save profile to localStorage:', e);
  }
}

export function useProfile() {
  const [profile, setProfileState] = useState<UserProfile>(loadProfile);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Sync to localStorage on changes
  useEffect(() => {
    saveProfile(profile);
  }, [profile]);

  const setTopics = useCallback((topics: string[]) => {
    setProfileState((prev) => ({
      ...prev,
      topics: topics.slice(0, MAX_TOPICS),
    }));
  }, []);

  const toggleTopic = useCallback((topic: string) => {
    setProfileState((prev) => {
      const exists = prev.topics.includes(topic);
      if (exists) {
        return { ...prev, topics: prev.topics.filter((t) => t !== topic) };
      } else if (prev.topics.length < MAX_TOPICS) {
        return { ...prev, topics: [...prev.topics, topic] };
      }
      return prev;
    });
  }, []);

  const setExperienceLevel = useCallback(
    (level: UserProfile['experienceLevel']) => {
      setProfileState((prev) => ({ ...prev, experienceLevel: level }));
    },
    []
  );

  const toggleFormat = useCallback(
    (format: 'in-person' | 'virtual' | 'hybrid') => {
      setProfileState((prev) => {
        const exists = prev.preferredFormats.includes(format);
        if (exists) {
          return {
            ...prev,
            preferredFormats: prev.preferredFormats.filter((f) => f !== format),
          };
        }
        return { ...prev, preferredFormats: [...prev.preferredFormats, format] };
      });
    },
    []
  );

  const markViewed = useCallback((cfpId: string) => {
    setProfileState((prev) => {
      if (prev.viewedCFPs.includes(cfpId)) return prev;
      const newViewed = [cfpId, ...prev.viewedCFPs].slice(0, MAX_VIEWED);
      return { ...prev, viewedCFPs: newViewed };
    });
  }, []);

  const toggleSaved = useCallback((cfpId: string) => {
    setProfileState((prev) => {
      const exists = prev.savedCFPs.includes(cfpId);
      if (exists) {
        return { ...prev, savedCFPs: prev.savedCFPs.filter((id) => id !== cfpId) };
      } else if (prev.savedCFPs.length < MAX_SAVED) {
        return { ...prev, savedCFPs: [cfpId, ...prev.savedCFPs] };
      }
      return prev;
    });
  }, []);

  const isSaved = useCallback(
    (cfpId: string) => profile.savedCFPs.includes(cfpId),
    [profile.savedCFPs]
  );

  // Talk tracking - mark as watched (goes to front, trimmed to 50)
  const markTalkWatched = useCallback((talkId: string) => {
    setProfileState((prev) => {
      // Move to front if already watched, otherwise add
      const filtered = prev.watchedTalks.filter((id) => id !== talkId);
      const newWatched = [talkId, ...filtered].slice(0, MAX_WATCHED_TALKS);
      return { ...prev, watchedTalks: newWatched };
    });
  }, []);

  // Talk favorites - toggle bookmark
  const toggleFavoriteTalk = useCallback((talkId: string) => {
    setProfileState((prev) => {
      const exists = prev.favoriteTalks.includes(talkId);
      if (exists) {
        return { ...prev, favoriteTalks: prev.favoriteTalks.filter((id) => id !== talkId) };
      } else if (prev.favoriteTalks.length < MAX_FAVORITE_TALKS) {
        return { ...prev, favoriteTalks: [talkId, ...prev.favoriteTalks] };
      }
      return prev;
    });
  }, []);

  const isFavoriteTalk = useCallback(
    (talkId: string) => profile.favoriteTalks.includes(talkId),
    [profile.favoriteTalks]
  );

  const isTalkWatched = useCallback(
    (talkId: string) => profile.watchedTalks.includes(talkId),
    [profile.watchedTalks]
  );

  // Speaker following
  const toggleFavoriteSpeaker = useCallback((speakerId: string) => {
    setProfileState((prev) => {
      const exists = prev.favoriteSpeakers.includes(speakerId);
      if (exists) {
        return { ...prev, favoriteSpeakers: prev.favoriteSpeakers.filter((id) => id !== speakerId) };
      } else if (prev.favoriteSpeakers.length < MAX_FAVORITE_SPEAKERS) {
        return { ...prev, favoriteSpeakers: [speakerId, ...prev.favoriteSpeakers] };
      }
      return prev;
    });
  }, []);

  const isFollowingSpeaker = useCallback(
    (speakerId: string) => profile.favoriteSpeakers.includes(speakerId),
    [profile.favoriteSpeakers]
  );

  const hasProfile = profile.topics.length > 0;
  const hasInterview = !!profile.interview?.interviewedAt;

  const resetProfile = useCallback(() => {
    setProfileState({ ...DEFAULT_PROFILE });
  }, []);

  // Interview profile - set from AI conversation
  const setInterview = useCallback((interview: UserProfile['interview']) => {
    setProfileState((prev) => ({ ...prev, interview }));
  }, []);

  const openProfile = useCallback(() => setIsProfileOpen(true), []);
  const closeProfile = useCallback(() => setIsProfileOpen(false), []);

  return {
    profile,
    hasProfile,
    hasInterview,
    isProfileOpen,
    openProfile,
    closeProfile,
    setTopics,
    toggleTopic,
    setExperienceLevel,
    toggleFormat,
    markViewed,
    toggleSaved,
    isSaved,
    // Talk & Speaker tracking
    markTalkWatched,
    toggleFavoriteTalk,
    isFavoriteTalk,
    isTalkWatched,
    toggleFavoriteSpeaker,
    isFollowingSpeaker,
    resetProfile,
    // Interview profile
    setInterview,
  };
}

// Available topics for the interest picker
export const AVAILABLE_TOPICS = [
  'AI/ML',
  'DevOps',
  'Frontend',
  'Backend',
  'Cloud',
  'Security',
  'Data',
  'Mobile',
  'Testing',
  'Platform',
  'Open Source',
  'Web3',
  'IoT',
  'Gaming',
  'API',
];
