import { useCallback, useState } from 'react';
import { Upload, File, X } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from './ui/button';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  maxSize?: number; // in MB
}

export default function FileUpload({
  onFileSelect,
  accept = '.csv,.txt',
  maxSize = 50,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const validateFile = (file: File): boolean => {
    // Check file type
    const extension = file.name.split('.').pop()?.toLowerCase();
    const allowedExtensions = accept.split(',').map((ext) => ext.trim().replace('.', ''));
    
    if (!extension || !allowedExtensions.includes(extension)) {
      toast.error(`Invalid file type. Allowed: ${accept}`);
      return false;
    }

    // Check file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > maxSize) {
      toast.error(`File too large. Maximum size: ${maxSize}MB`);
      return false;
    }

    return true;
  };

  const handleFile = useCallback(
    (file: File) => {
      if (validateFile(file)) {
        setSelectedFile(file);
        onFileSelect(file);
        toast.success(`File selected: ${file.name}`);
      }
    },
    [onFileSelect, accept, maxSize]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  const clearFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  return (
    <div className="w-full">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`relative border-2 border-dashed rounded-xl p-8 transition-all duration-200 ease-in-out ${
          isDragging
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30'
        }`}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          accept={accept}
          onChange={handleFileInput}
        />

        {!selectedFile ? (
          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center cursor-pointer group"
          >
            <div className="p-4 rounded-full bg-muted group-hover:bg-primary/10 transition-colors mb-4">
              <Upload className="h-8 w-8 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="text-lg font-medium text-foreground mb-2">
              Drop your CSV file here
            </p>
            <p className="text-sm text-muted-foreground mb-1">
              or click to browse
            </p>
            <p className="text-xs text-muted-foreground/70 mt-2">
              Supports WinPEP, PowerVision, and generic CSV formats (Max {maxSize}MB)
            </p>
          </label>
        ) : (
          <div className="flex items-center justify-between p-2">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-lg bg-primary/10">
                <File className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-muted-foreground font-mono">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.preventDefault();
                clearFile();
              }}
              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
