import { ChatApp } from './ChatApp';
import { useAuth } from '../hooks/useAuth';
import { Navigate } from 'react-router-dom';

const Index = () => {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <ChatApp />;
};

export default Index;
