// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { matchPath } from 'react-router-dom';
import { useGetMyAuthorizedMenusApiV1AdminMeMenusGet } from '../services/api/endpoints';
import type { AuthorizedMenuResponse } from '../services/api/schemas';
import { jwtDecode } from 'jwt-decode';

interface DecodedToken {
  sub: string;
  roles: string[];
  mfa_enabled: boolean;
  exp: number;
}
interface UserState {
  username: string;
  roles: string[];
  isMfaEnabled: boolean;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserState | null;
  login: (token: string) => void;
  logout: () => void;
  isLoading: boolean;
  authorizedMenus: AuthorizedMenuResponse[];
  isLoadingMenus: boolean; // <--- AÑADIDO
  hasAccessToRoute: (path: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [sessionToken, setSessionToken] = useState<string | null>(() => localStorage.getItem('session_token'));
  const [user, setUser] = useState<UserState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    try {
      if (sessionToken) {
        const decoded = jwtDecode<DecodedToken>(sessionToken);
        if (decoded.exp * 1000 > Date.now()) {
          setUser({
            username: decoded.sub,
            roles: decoded.roles || [],
            isMfaEnabled: decoded.mfa_enabled || false,
          });
        } else {
          localStorage.removeItem('session_token');
          setSessionToken(null);
        }
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error("Token inválido, limpiando sesión.", error);
      localStorage.removeItem('session_token');
      setSessionToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken]);

  const login = (token: string) => {
    localStorage.setItem('session_token', token);
    setSessionToken(token);
  };

  const logout = () => {
    localStorage.removeItem('session_token');
    setSessionToken(null);
  };

  const { data: menuData, isLoading: isLoadingMenus } = useGetMyAuthorizedMenusApiV1AdminMeMenusGet({
    query: {
      enabled: !!sessionToken,
    },
  });

  const authorizedMenus = menuData || [];
  
  const hasAccessToRoute = useCallback((path: string): boolean => {
    if (!user) return false;
    if (user.roles.includes('SuperAdmin')) return true;
    
    // Si los menús aún están cargando, denegamos el acceso temporalmente
    if (isLoadingMenus) return false; 
    
    if (path === '/admin' || path === '/admin/') return true;
    
    return authorizedMenus.some(menu => !!matchPath(menu.frontend_route, path));
  }, [user, authorizedMenus, isLoadingMenus]);


  const value: AuthContextType = {
    isAuthenticated: !!user,
    user,
    login,
    logout,
    isLoading,
    authorizedMenus,
    isLoadingMenus, // <--- AÑADIDO
    hasAccessToRoute,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};