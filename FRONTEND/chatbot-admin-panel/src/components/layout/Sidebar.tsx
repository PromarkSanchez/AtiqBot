// src/components/layout/Sidebar.tsx
import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import type { AuthorizedMenuResponse } from '../../services/api/schemas';

// --- ¡NUEVA FORMA DE IMPORTAR ICONOS! ---
// Importamos TODOS los iconos de 'outline' en un solo objeto llamado 'OutlineIcons'
import * as OutlineIcons from '@heroicons/react/24/outline';

// Opcional: Si también usas iconos sólidos, puedes hacer lo mismo
// import * as SolidIcons from '@heroicons/react/24/solid';

// Definimos un componente por defecto que se usará si un icono no se encuentra
const DefaultIcon = OutlineIcons.Cog6ToothIcon;

// Tipos para props y para los menús procesados
interface SidebarProps {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

interface ProcessedMenuItem extends AuthorizedMenuResponse {
  children: ProcessedMenuItem[];
}

const Sidebar: React.FC<SidebarProps> = ({ sidebarOpen, setSidebarOpen }) => {
  const { authorizedMenus, isLoadingMenus } = useAuth();

  // La lógica para estructurar menús en padres/hijos no cambia
  const processedMenus = React.useMemo(() => {
    // ... (tu lógica de useMemo para anidar menús sigue igual aquí) ...
    const menuMap: Record<number, ProcessedMenuItem> = {};
    const rootMenus: ProcessedMenuItem[] = [];
    authorizedMenus.forEach(menu => {
      menuMap[menu.id] = { ...menu, children: [] };
    });
    Object.values(menuMap).forEach(menu => {
      if (menu.parent_id && menuMap[menu.parent_id]) {
        menuMap[menu.parent_id].children.push(menu);
      } else {
        rootMenus.push(menu);
      }
    });
    Object.values(menuMap).forEach(menu => {
      menu.children.sort((a, b) => a.display_order - b.display_order);
    });
    return rootMenus.sort((a, b) => a.display_order - b.display_order);
  }, [authorizedMenus]);
  
  // --- FUNCIÓN DE RENDERIZADO SIMPLIFICADA ---
  const renderMenuItems = (menus: ProcessedMenuItem[]) => {
    return menus.map(menu => {
      // Búsqueda dinámica del icono. Si no se encuentra, usa el DefaultIcon.
      const IconComponent = (OutlineIcons as any)[menu.icon_name || ''] || DefaultIcon;

      // La lógica para menús con hijos sigue igual
      if (menu.children && menu.children.length > 0) {
        return (
          <div key={menu.id}>
            <span className="flex items-center px-4 py-2 mt-2 text-sm font-semibold text-gray-500 dark:text-gray-400">
              <IconComponent className="h-5 w-5 mr-3" />
              {menu.name}
            </span>
            <ul className="pl-4">
              {renderMenuItems(menu.children)}
            </ul>
          </div>
        );
      }

      // El NavLink para menús sin hijos también sigue igual
      return (
        <li key={menu.id}>
          <NavLink
            to={menu.frontend_route}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center px-4 py-2 mt-1 text-sm font-medium rounded-md transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-700'
              }`
            }
          >
            <IconComponent className="h-5 w-5 mr-3" />
            {menu.name}
          </NavLink>
        </li>
      );
    });
  };

  // El resto del JSX del componente (return de Sidebar) no cambia
  return (
    <>
      {/* Overlay para móvil */}
      <div 
        className={`fixed inset-0 bg-black bg-opacity-50 z-20 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}
        onClick={() => setSidebarOpen(false)}
      ></div>

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full w-64 bg-white dark:bg-slate-800 shadow-xl z-30
                    transform transition-transform ease-in-out duration-300 lg:relative lg:translate-x-0
                    ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-slate-700">
          <Link to="/admin" className="text-xl font-bold text-indigo-600 dark:text-indigo-400">
            <img src="/favicon.ico" alt="Logo" className="h-8 w-8 inline-block mr-2" />
            Chatbot Admin
          </Link>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 text-gray-500 dark:text-gray-300">
            <OutlineIcons.XMarkIcon className="h-6 w-6"/>
          </button>
        </div>
        
        <nav className="p-4">
          <ul>
            {isLoadingMenus ? (
              <div className="space-y-4">
                {[...Array(6)].map((_, i) => ( <div key={i} className="h-8 bg-gray-200 dark:bg-slate-700 rounded animate-pulse"></div> ))}
              </div>
            ) : (
              renderMenuItems(processedMenus)
            )}
          </ul>
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;