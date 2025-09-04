import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import config_utils

class BackupLogParser:
    """Parser for BorgBackup logs based on configurable keywords"""
    
    def __init__(self):
        self.backup_config = config_utils.get_backup_config()
        self.keywords = self.backup_config.get("keywords", {})
        self.datetime_format = self.backup_config.get("datetime_format", "%Y-%m-%d %H:%M:%S")
        self.logs_dir = "data/backup_logs"
    
    def parse_logs(self) -> List[Dict[str, Any]]:
        """Parse all backup log files in the backup_logs directory"""
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir, exist_ok=True)
            return []
        
        all_backups = []
        
        # Get all log files
        for filename in os.listdir(self.logs_dir):
            if filename.endswith(('.log', '.txt')):
                log_path = os.path.join(self.logs_dir, filename)
                try:
                    backup_data = self._parse_log_file(log_path)
                    if backup_data:
                        backup_data['log_file'] = filename
                        all_backups.append(backup_data)
                except Exception as e:
                    print(f"Error parsing {filename}: {e}")
        
        # Sort by date (most recent first)
        # Handle None timestamps by putting them at the end
        all_backups.sort(key=lambda x: x.get('timestamp') or '1970-01-01', reverse=True)
        return all_backups
    
    def _parse_log_file(self, log_path: str) -> Optional[Dict[str, Any]]:
        """Parse a single backup log file"""
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file {log_path}: {e}")
            return None
        
        backup_data = {
            'timestamp': None,
            'archive_name': None,
            'repository': None,
            'location': None,
            'backup_size': None,
            'original_size': None,
            'compressed_size': None,
            'deduplicated_size': None,
            'number_files': None,
            'added_files': None,
            'modified_files': None,
            'unchanged_files': None,
            'duration': None,
            'start_time': None,
            'end_time': None,
            'status': None,
            'success': False
        }
        
        # Extract information based on keywords
        for field, keyword in self.keywords.items():
            if keyword:
                backup_data[field] = self._extract_field(content, keyword, field)
        
        # Try to parse dates
        self._parse_timestamps(backup_data)
        
        # Determine if backup was successful
        if backup_data['status']:
            backup_data['success'] = 'success' in backup_data['status'].lower() or 'completed' in backup_data['status'].lower()
        
        # Only return if we found at least some useful data
        has_data = any([
            backup_data.get('archive_name'),
            backup_data.get('start_time'),
            backup_data.get('backup_size'),
            backup_data.get('status')
        ])
        
        return backup_data if has_data else None
    
    def _extract_field(self, content: str, keyword: str, field_type: str) -> Optional[str]:
        """Extract a field value based on keyword"""
        # Create regex pattern to find the keyword and capture the value after it
        patterns = [
            rf'{re.escape(keyword)}[:\s]+([^\n\r]+)',  # Keyword: value
            rf'{re.escape(keyword)}\s+([^\n\r]+)',     # Keyword value
            rf'({re.escape(keyword)}[^\n\r]*)',        # Line containing keyword
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                
                # Clean up common prefixes/suffixes
                value = re.sub(r'^[:\-=>\s]+', '', value)
                value = re.sub(r'[,;\s]+$', '', value)
                
                return value if value else None
        
        return None
    
    def _parse_timestamps(self, backup_data: Dict[str, Any]):
        """Parse timestamp fields into proper datetime objects"""
        timestamp_fields = ['start_time', 'end_time']
        
        for field in timestamp_fields:
            if backup_data.get(field):
                try:
                    # Try multiple common datetime formats
                    formats = [
                        self.datetime_format,
                        '%Y-%m-%d %H:%M:%S',
                        '%Y/%m/%d %H:%M:%S',
                        '%d-%m-%Y %H:%M:%S',
                        '%Y-%m-%d %H:%M',
                        '%Y-%m-%dT%H:%M:%S',
                        '%a %b %d %H:%M:%S %Y'
                    ]
                    
                    parsed_time = None
                    for fmt in formats:
                        try:
                            parsed_time = datetime.strptime(backup_data[field], fmt)
                            break
                        except ValueError:
                            continue
                    
                    if parsed_time:
                        backup_data[f'{field}_parsed'] = parsed_time.isoformat()
                        if not backup_data.get('timestamp'):
                            backup_data['timestamp'] = parsed_time.isoformat()
                    else:
                        print(f"Could not parse timestamp '{backup_data[field]}' in field '{field}'")
                            
                except Exception as e:
                    print(f"Error parsing timestamp for {field}: {e}")
        
        # If we still don't have a timestamp, try to create one from available data
        if not backup_data.get('timestamp'):
            # Use current time as fallback
            backup_data['timestamp'] = datetime.now().isoformat()
            print(f"No valid timestamp found, using current time as fallback")
    
    def get_latest_backup(self) -> Optional[Dict[str, Any]]:
        """Get the most recent backup"""
        backups = self.parse_logs()
        return backups[0] if backups else None
    
    def get_backup_summary(self) -> Dict[str, Any]:
        """Get a summary of all backups"""
        try:
            backups = self.parse_logs()
        except Exception as e:
            print(f"Error parsing logs: {e}")
            return {
                'total_backups': 0,
                'successful_backups': 0,
                'failed_backups': 0,
                'last_backup': None,
                'oldest_backup': None,
                'total_size': None,
                'status': 'error'
            }
        
        if not backups:
            return {
                'total_backups': 0,
                'successful_backups': 0,
                'failed_backups': 0,
                'last_backup': None,
                'oldest_backup': None,
                'total_size': None,
                'status': 'no_data'
            }
        
        successful = [b for b in backups if b.get('success')]
        failed = [b for b in backups if not b.get('success')]
        
        # Calculate total size if available
        total_size = None
        if backups[0].get('backup_size'):
            # This is a simplified approach - you might want more sophisticated size calculation
            total_size = backups[0]['backup_size']
        
        return {
            'total_backups': len(backups),
            'successful_backups': len(successful),
            'failed_backups': len(failed),
            'last_backup': backups[0] if backups else None,
            'oldest_backup': backups[-1] if backups else None,
            'total_size': total_size,
            'status': 'healthy' if len(successful) > 0 and len(failed) == 0 else 'warning' if len(failed) > 0 else 'unknown'
        }


class SmartDataParser:
    """Parser for SMART data logs"""
    
    def __init__(self):
        self.backup_config = config_utils.get_backup_config()
        self.smart_format = self.backup_config.get("smart_log_format", "smartctl-json")
        self.datetime_format = self.backup_config.get("smart_datetime_format", "%Y-%m-%d %H:%M:%S")
        self.logs_dir = "data/smart_logs"
        
        # Monitoring settings
        self.monitor_temp = self.backup_config.get("smart_temp_monitoring", True)
        self.monitor_health = self.backup_config.get("smart_health_monitoring", True)
        self.monitor_attributes = self.backup_config.get("smart_attribute_monitoring", True)
    
    def parse_logs(self) -> List[Dict[str, Any]]:
        """Parse all SMART data log files"""
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir, exist_ok=True)
            return []
        
        all_drives = []
        
        for filename in os.listdir(self.logs_dir):
            if filename.endswith(('.log', '.txt', '.json')):
                log_path = os.path.join(self.logs_dir, filename)
                try:
                    drive_data = self._parse_smart_file(log_path)
                    if drive_data:
                        drive_data['log_file'] = filename
                        all_drives.append(drive_data)
                except Exception as e:
                    print(f"Error parsing SMART data {filename}: {e}")
        
        return all_drives
    
    def _parse_smart_file(self, log_path: str) -> Optional[Dict[str, Any]]:
        """Parse a single SMART data file"""
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if self.smart_format == "smartctl-json":
            return self._parse_smartctl_json(content)
        elif self.smart_format == "smartctl-text":
            return self._parse_smartctl_text(content)
        else:
            return self._parse_custom_format(content)
    
    def _parse_smartctl_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse smartctl JSON output"""
        try:
            data = json.loads(content)
            
            result = {
                'device': data.get('device', {}).get('name', 'Unknown'),
                'model': data.get('model_name', 'Unknown'),
                'serial': data.get('serial_number', 'Unknown'),
                'health_status': 'unknown',
                'temperature': None,
                'attributes': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # Health status
            if 'smart_status' in data:
                result['health_status'] = 'healthy' if data['smart_status'].get('passed') else 'failed'
            
            # Temperature
            if 'temperature' in data:
                result['temperature'] = data['temperature'].get('current')
            
            # SMART attributes
            if 'ata_smart_attributes' in data and 'table' in data['ata_smart_attributes']:
                for attr in data['ata_smart_attributes']['table']:
                    attr_name = attr.get('name', f"ID_{attr.get('id')}")
                    result['attributes'][attr_name] = {
                        'id': attr.get('id'),
                        'value': attr.get('value'),
                        'raw_value': attr.get('raw', {}).get('value'),
                        'threshold': attr.get('thresh'),
                        'status': 'ok' if attr.get('value', 0) > attr.get('thresh', 0) else 'warning'
                    }
            
            return result
            
        except json.JSONDecodeError:
            return None
    
    def _parse_smartctl_text(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse smartctl text output"""
        result = {
            'device': 'Unknown',
            'model': 'Unknown', 
            'serial': 'Unknown',
            'health_status': 'unknown',
            'temperature': None,
            'attributes': {},
            'timestamp': datetime.now().isoformat()
        }
        
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Device info
            if 'Device Model:' in line:
                result['model'] = line.split(':', 1)[1].strip()
            elif 'Serial Number:' in line:
                result['serial'] = line.split(':', 1)[1].strip()
            elif 'Device:' in line and result['device'] == 'Unknown':
                result['device'] = line.split(':', 1)[1].strip()
            
            # Health status
            elif 'SMART overall-health' in line:
                if 'PASSED' in line:
                    result['health_status'] = 'healthy'
                elif 'FAILED' in line:
                    result['health_status'] = 'failed'
            
            # Temperature
            elif 'Temperature' in line and '°C' in line:
                temp_match = re.search(r'(\d+)°C', line)
                if temp_match:
                    result['temperature'] = int(temp_match.group(1))
        
        return result
    
    def _parse_custom_format(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse custom SMART data format"""
        # Implement custom parsing logic here
        # This is a placeholder for user-defined formats
        return {
            'device': 'Custom',
            'model': 'Unknown',
            'serial': 'Unknown',
            'health_status': 'unknown',
            'temperature': None,
            'attributes': {},
            'timestamp': datetime.now().isoformat()
        }
    
    def get_drive_summary(self) -> Dict[str, Any]:
        """Get summary of all drives"""
        drives = self.parse_logs()
        
        if not drives:
            return {
                'total_drives': 0,
                'healthy_drives': 0,
                'warning_drives': 0,
                'failed_drives': 0,
                'average_temp': None,
                'max_temp': None,
                'status': 'no_data'
            }
        
        healthy = [d for d in drives if d.get('health_status') == 'healthy']
        failed = [d for d in drives if d.get('health_status') == 'failed']
        warning = [d for d in drives if d.get('health_status') not in ['healthy', 'failed']]
        
        # Temperature stats
        temps = [d['temperature'] for d in drives if d.get('temperature') is not None]
        avg_temp = sum(temps) / len(temps) if temps else None
        max_temp = max(temps) if temps else None
        
        overall_status = 'healthy'
        if len(failed) > 0:
            overall_status = 'critical'
        elif len(warning) > 0:
            overall_status = 'warning'
        
        return {
            'total_drives': len(drives),
            'healthy_drives': len(healthy),
            'warning_drives': len(warning),
            'failed_drives': len(failed),
            'average_temp': avg_temp,
            'max_temp': max_temp,
            'status': overall_status,
            'drives': drives
        }
