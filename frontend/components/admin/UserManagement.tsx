'use client';

import React, { useState, useEffect } from 'react';
import { adminApi, UserResponse, UserTableauMappingResponse, UserTableauMappingCreate, UserTableauMappingUpdate, TableauConfigResponse, UserUpdate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Trash2, Plus, X, Server, Edit2 } from 'lucide-react';

interface UserCreate {
  username: string;
  password: string;
  role: string;
}

export function UserManagement() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<UserCreate>({
    username: '',
    password: '',
    role: 'USER'
  });
  const [expandedUsers, setExpandedUsers] = useState<Set<number>>(new Set());
  const [userMappings, setUserMappings] = useState<Map<number, UserTableauMappingResponse[]>>(new Map());
  const [tableauConfigs, setTableauConfigs] = useState<TableauConfigResponse[]>([]);
  const [showMappingForm, setShowMappingForm] = useState<number | null>(null);
  const [mappingFormData, setMappingFormData] = useState<UserTableauMappingCreate>({
    user_id: 0,
    tableau_server_config_id: 0,
    tableau_username: ''
  });
  const [editingUser, setEditingUser] = useState<UserResponse | null>(null);
  const [editFormData, setEditFormData] = useState<UserUpdate & { password: string }>({
    username: '',
    password: '',
    role: 'USER',
    is_active: true
  });

  useEffect(() => {
    loadUsers();
    loadTableauConfigs();
  }, []);

  const loadTableauConfigs = async () => {
    try {
      const configs = await adminApi.listTableauConfigs();
      setTableauConfigs(configs);
    } catch (err) {
      console.error('Failed to load Tableau configs:', err);
    }
  };

  const loadUserMappings = async (userId: number) => {
    try {
      const mappings = await adminApi.listUserTableauMappings(userId);
      setUserMappings(new Map(userMappings).set(userId, mappings));
    } catch (err) {
      console.error(`Failed to load mappings for user ${userId}:`, err);
    }
  };

  const handleToggleUser = (userId: number) => {
    const newExpanded = new Set(expandedUsers);
    if (newExpanded.has(userId)) {
      newExpanded.delete(userId);
    } else {
      newExpanded.add(userId);
      if (!userMappings.has(userId)) {
        loadUserMappings(userId);
      }
    }
    setExpandedUsers(newExpanded);
  };

  const handleCreateMapping = async (userId: number) => {
    try {
      setError(null);
      await adminApi.createUserTableauMapping(userId, {
        ...mappingFormData,
        user_id: userId
      });
      setShowMappingForm(null);
      setMappingFormData({ user_id: 0, tableau_server_config_id: 0, tableau_username: '' });
      loadUserMappings(userId);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create mapping');
    }
  };

  const handleUpdateMapping = async (userId: number, mappingId: number, tableauUsername: string) => {
    try {
      setError(null);
      await adminApi.updateUserTableauMapping(userId, mappingId, { 
        tableau_username: tableauUsername
      });
      loadUserMappings(userId);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to update mapping');
    }
  };

  const handleDeleteMapping = async (userId: number, mappingId: number) => {
    if (!confirm('Are you sure you want to delete this mapping?')) return;
    try {
      setError(null);
      await adminApi.deleteUserTableauMapping(userId, mappingId);
      loadUserMappings(userId);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete mapping');
    }
  };

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Debug: Check if token exists
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setError('No authentication token found. Please log in again.');
        return;
      }
      
      const usersList = await adminApi.listUsers();
      setUsers(usersList);
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || err.message || 'Failed to load users';
      console.error('Error loading users:', err);
      console.error('Error response:', err.response);
      setError(errorDetail);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError(null);
      await adminApi.createUser(formData);
      setShowCreateForm(false);
      setFormData({ username: '', password: '', role: 'USER' });
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create user');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('Are you sure you want to permanently delete this user? This action cannot be undone. All associated Tableau configurations, provider configurations, and mappings will also be deleted.')) return;
    try {
      setError(null);
      await adminApi.deleteUser(userId);
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete user');
    }
  };

  const handleStartEdit = (user: UserResponse) => {
    setEditingUser(user);
    setEditFormData({
      username: user.username,
      password: '',
      role: user.role,
      is_active: user.is_active
    });
    // Load mappings if not already loaded
    if (!userMappings.has(user.id)) {
      loadUserMappings(user.id);
    }
  };

  const handleCancelEdit = () => {
    setEditingUser(null);
    setEditFormData({
      username: '',
      password: '',
      role: 'USER',
      is_active: true
    });
    setShowMappingForm(null);
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;
    
    try {
      setError(null);
      const updateData: UserUpdate = {
        username: editFormData.username,
        role: editFormData.role,
        is_active: editFormData.is_active
      };
      
      // Only include password if it's been changed
      if (editFormData.password) {
        updateData.password = editFormData.password;
      }
      
      await adminApi.updateUser(editingUser.id, updateData);
      setEditingUser(null);
      setEditFormData({
        username: '',
        password: '',
        role: 'USER',
        is_active: true
      });
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to update user');
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading users...</div>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">{error}</Alert>
      )}

      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Users</h2>
        <Button 
          onClick={() => setShowCreateForm(!showCreateForm)}
          title={showCreateForm ? 'Cancel' : 'Add User'}
        >
          {showCreateForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
        </Button>
      </div>

      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New User</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <Select
                  value={formData.role}
                  onValueChange={(value) => setFormData({ ...formData, role: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USER">User</SelectItem>
                    <SelectItem value="ADMIN">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2">
                <Button 
                  type="submit"
                  title="Create User"
                >
                  <Plus className="h-4 w-4" />
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => {
                    setShowCreateForm(false);
                    setFormData({ username: '', password: '', role: 'USER' });
                  }}
                  title="Cancel"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="border rounded-lg overflow-x-auto">
        <table className="w-full min-w-full">
          <thead className="bg-gray-100 dark:bg-gray-800">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">Username</th>
              <th className="px-4 py-2 text-left">Role</th>
              <th className="px-4 py-2 text-left">Status</th>
              <th className="px-4 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const isExpanded = expandedUsers.has(user.id);
              const mappings = userMappings.get(user.id) || [];
              return (
                <React.Fragment key={user.id}>
                  <tr className="border-t">
                    <td className="px-4 py-2">{user.id}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleUser(user.id)}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                        >
                          {isExpanded ? '▼' : '▶'}
                        </button>
                        <div>
                          <div>{user.username}</div>
                          {user.tableau_username && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              Tableau: {user.tableau_username}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2">{user.role}</td>
                    <td className="px-4 py-2">
                      <span className={user.is_active ? 'text-green-600' : 'text-red-600'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleStartEdit(user)}
                          title="Edit User"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDeleteUser(user.id)}
                          title="Delete User"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={5} className="px-4 py-4 bg-gray-50 dark:bg-gray-800">
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold flex items-center gap-2">
                              <Server className="h-4 w-4" />
                              Tableau Connected App Mappings
                            </h3>
                            <Button
                              size="sm"
                              onClick={() => {
                                setShowMappingForm(user.id);
                                setMappingFormData({
                                  user_id: user.id,
                                  tableau_server_config_id: tableauConfigs[0]?.id || 0,
                                  tableau_username: ''
                                });
                              }}
                            >
                              <Plus className="h-4 w-4 mr-1" />
                              Add Mapping
                            </Button>
                          </div>
                          
                          {showMappingForm === user.id && (
                            <Card>
                              <CardHeader>
                                <CardTitle>Create Tableau Server Mapping</CardTitle>
                              </CardHeader>
                              <CardContent>
                                <form onSubmit={(e) => { e.preventDefault(); handleCreateMapping(user.id); }} className="space-y-4">
                                  <div className="space-y-2">
                                    <Label htmlFor="tableau_config">Tableau Connected App</Label>
                                    <Select
                                      value={mappingFormData.tableau_server_config_id.toString()}
                                      onValueChange={(value) => setMappingFormData({ ...mappingFormData, tableau_server_config_id: parseInt(value) })}
                                    >
                                      <SelectTrigger>
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {tableauConfigs.map((config) => {
                                          const siteDisplay = config.site_id && config.site_id.trim() ? config.site_id : 'Default';
                                          return (
                                            <SelectItem key={config.id} value={config.id.toString()}>
                                              {config.name} ({config.server_url}, {siteDisplay})
                                            </SelectItem>
                                          );
                                        })}
                                      </SelectContent>
                                    </Select>
                                  </div>
                                  <div className="space-y-2">
                                    <Label htmlFor="tableau_username">Tableau Username</Label>
                                    <Input
                                      id="tableau_username"
                                      value={mappingFormData.tableau_username}
                                      onChange={(e) => setMappingFormData({ ...mappingFormData, tableau_username: e.target.value })}
                                      placeholder="Enter Tableau server username"
                                      required
                                    />
                                  </div>
                                  <div className="flex gap-2">
                                    <Button type="submit">
                                      <Plus className="h-4 w-4 mr-1" />
                                      Create
                                    </Button>
                                    <Button
                                      type="button"
                                      variant="outline"
                                      onClick={() => {
                                        setShowMappingForm(null);
                                        setMappingFormData({ user_id: 0, tableau_server_config_id: 0, tableau_username: '' });
                                      }}
                                    >
                                      <X className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </form>
                              </CardContent>
                            </Card>
                          )}
                          
                          {mappings.length === 0 ? (
                            <p className="text-sm text-gray-500 dark:text-gray-400">No mappings configured</p>
                          ) : (
                            <div className="space-y-2">
                              {mappings.map((mapping) => {
                                const config = tableauConfigs.find(c => c.id === mapping.tableau_server_config_id);
                                return (
                                  <Card key={mapping.id}>
                                    <CardContent className="pt-4">
                                      <div className="flex items-center justify-between">
                                        <div className="flex-1">
                                          <p className="font-medium">{config?.name || `Config ${mapping.tableau_server_config_id}`}</p>
                                          <p className="text-sm text-gray-500 dark:text-gray-400">
                                            {config?.server_url && (
                                              <span>{config.server_url}{config?.site_id && config.site_id.trim() ? `, Site: ${config.site_id}` : ', Site: Default'} | </span>
                                            )}
                                            Username: {mapping.tableau_username}
                                          </p>
                                        </div>
                                        <div className="flex gap-2">
                                          <Input
                                            type="text"
                                            defaultValue={mapping.tableau_username}
                                            onBlur={(e) => {
                                              if (e.target.value !== mapping.tableau_username) {
                                                handleUpdateMapping(user.id, mapping.id, e.target.value);
                                              }
                                            }}
                                            onKeyDown={(e) => {
                                              if (e.key === 'Enter') {
                                                e.currentTarget.blur();
                                              }
                                            }}
                                            className="w-48"
                                          />
                                          <Button
                                            variant="destructive"
                                            size="sm"
                                            onClick={() => handleDeleteMapping(user.id, mapping.id)}
                                          >
                                            <Trash2 className="h-4 w-4" />
                                          </Button>
                                        </div>
                                      </div>
                                    </CardContent>
                                  </Card>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Edit User Dialog */}
      <Dialog open={editingUser !== null} onOpenChange={(open) => !open && handleCancelEdit()}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>
              Update user information and manage Tableau server mappings
            </DialogDescription>
          </DialogHeader>
          
          {editingUser && (
            <div className="space-y-6 py-4">
              {/* User Information */}
              <div className="space-y-4">
                <h3 className="font-semibold text-lg">User Information</h3>
                
                <div className="space-y-2">
                  <Label htmlFor="edit-username">Username</Label>
                  <Input
                    id="edit-username"
                    value={editFormData.username}
                    onChange={(e) => setEditFormData({ ...editFormData, username: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-password">Password (leave blank to keep current)</Label>
                  <Input
                    id="edit-password"
                    type="password"
                    value={editFormData.password}
                    onChange={(e) => setEditFormData({ ...editFormData, password: e.target.value })}
                    placeholder="Enter new password or leave blank"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-role">Role</Label>
                  <Select
                    value={editFormData.role}
                    onValueChange={(value) => setEditFormData({ ...editFormData, role: value as 'USER' | 'ADMIN' })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USER">User</SelectItem>
                      <SelectItem value="ADMIN">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-status">Status</Label>
                  <Select
                    value={editFormData.is_active ? 'active' : 'inactive'}
                    onValueChange={(value) => setEditFormData({ ...editFormData, is_active: value === 'active' })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Tableau Server Mappings */}
              <div className="space-y-4 border-t pt-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    <Server className="h-5 w-5" />
                    Tableau Connected App Mappings
                  </h3>
                  <Button
                    size="sm"
                    onClick={() => {
                      setShowMappingForm(editingUser.id);
                      setMappingFormData({
                        user_id: editingUser.id,
                        tableau_server_config_id: tableauConfigs[0]?.id || 0,
                        tableau_username: ''
                      });
                    }}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add Mapping
                  </Button>
                </div>

                {showMappingForm === editingUser.id && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Create Tableau Server Mapping</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={(e) => { e.preventDefault(); handleCreateMapping(editingUser.id); }} className="space-y-4">
                        <div className="space-y-2">
                          <Label htmlFor="dialog-tableau-config">Tableau Connected App</Label>
                          <Select
                            value={mappingFormData.tableau_server_config_id.toString()}
                            onValueChange={(value) => setMappingFormData({ ...mappingFormData, tableau_server_config_id: parseInt(value) })}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {tableauConfigs.map((config) => {
                                const siteDisplay = config.site_id && config.site_id.trim() ? config.site_id : 'Default';
                                return (
                                  <SelectItem key={config.id} value={config.id.toString()}>
                                    {config.name} ({config.server_url}, {siteDisplay})
                                  </SelectItem>
                                );
                              })}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="dialog-tableau-username">Tableau Username</Label>
                          <Input
                            id="dialog-tableau-username"
                            value={mappingFormData.tableau_username}
                            onChange={(e) => setMappingFormData({ ...mappingFormData, tableau_username: e.target.value })}
                            placeholder="Enter Tableau server username"
                            required
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button type="submit">
                            <Plus className="h-4 w-4 mr-1" />
                            Create
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              setShowMappingForm(null);
                              setMappingFormData({ user_id: 0, tableau_server_config_id: 0, tableau_username: '' });
                            }}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      </form>
                    </CardContent>
                  </Card>
                )}

                {userMappings.get(editingUser.id)?.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">No mappings configured</p>
                ) : (
                  <div className="space-y-2">
                    {userMappings.get(editingUser.id)?.map((mapping) => {
                      const config = tableauConfigs.find(c => c.id === mapping.tableau_server_config_id);
                      return (
                        <Card key={mapping.id}>
                          <CardContent className="pt-4">
                            <div className="flex items-center justify-between">
                              <div className="flex-1">
                                <p className="font-medium">{config?.name || `Config ${mapping.tableau_server_config_id}`}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                  {config?.server_url && (
                                    <span>{config.server_url}{config?.site_id && config.site_id.trim() ? `, Site: ${config.site_id}` : ', Site: Default'} | </span>
                                  )}
                                  Username: {mapping.tableau_username}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <Input
                                  type="text"
                                  defaultValue={mapping.tableau_username}
                                  onBlur={(e) => {
                                    if (e.target.value !== mapping.tableau_username) {
                                      handleUpdateMapping(editingUser.id, mapping.id, e.target.value);
                                    }
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      e.currentTarget.blur();
                                    }
                                  }}
                                  className="w-48"
                                />
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={() => handleDeleteMapping(editingUser.id, mapping.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={handleCancelEdit}>
              Cancel
            </Button>
            <Button onClick={handleSaveUser}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
