import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface AdminGuardProps {
  children: React.ReactNode;
}

/**
 * Route guard that checks for a valid admin JWT in localStorage.
 * Redirects to /admin/login if no token is found.
 * 
 * Note: This only checks token existence, not validity.
 * The backend validates tokens on each API call.
 */
const AdminGuard: React.FC<AdminGuardProps> = ({ children }) => {
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      navigate('/admin/login', { replace: true });
    } else {
      setChecked(true);
    }
  }, [navigate]);

  if (!checked) return null;
  return <>{children}</>;
};

export default AdminGuard;
