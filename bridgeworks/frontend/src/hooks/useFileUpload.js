import { useState, useRef } from 'react';
import { BACKEND_URL } from '../config/api';
import { apiClient } from "../apiClient";

export const useFileUpload = () => {
    const [files, setFiles] = useState({
        profile: null,
        aadhaar: null,
        pan: null
    });

    const [uploading, setUploading] = useState({
        profile: false,
        aadhaar: false,
        pan: false
    });

    const profileInputRef = useRef(null);
    const aadhaarInputRef = useRef(null);
    const panInputRef = useRef(null);

    const validateFile = (file, maxSize = 5 * 1024 * 1024) => {
        if (!file) return { valid: false, error: 'No file selected' };

        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
        if (!allowedTypes.includes(file.type)) {
            return { valid: false, error: 'Invalid file type. Only PDF, JPG, PNG allowed' };
        }

        if (file.size > maxSize) {
            return { valid: false, error: 'File size exceeds 5MB' };
        }

        return { valid: true };
    };

    const uploadFile = async (file, endpoint, fileType) => {
        const validation = validateFile(file);
        if (!validation.valid) {
            return { success: false, error: validation.error };
        }

        setUploading(prev => ({ ...prev, [fileType]: true }));
        const formData = new FormData();
        formData.append(fileType, file);

        try {
            const response = await apiClient(`${BACKEND_URL}${endpoint}`, {
                method: 'POST',
                credentials: 'include',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                setFiles(prev => ({ ...prev, [fileType]: file }));
                return { success: true, data };
            } else {
                return { success: false, error: 'Upload failed' };
            }
        } catch (error) {
            console.error(`Error uploading ${fileType}:`, error);
            return { success: false, error: 'Upload error' };
        } finally {
            setUploading(prev => ({ ...prev, [fileType]: false }));
        }
    };

    const removeFile = (fileType, inputRef) => {
        setFiles(prev => ({ ...prev, [fileType]: null }));
        if (inputRef.current) inputRef.current.value = '';
    };

    return {
        files,
        uploading,
        refs: { profileInputRef, aadhaarInputRef, panInputRef },
        uploadFile,
        removeFile,
        validateFile
    };
};
