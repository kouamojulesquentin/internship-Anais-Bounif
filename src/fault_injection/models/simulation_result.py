class SimulationResult(object):
    def __init__(self, run_id, fault_id, corner, simulation_status,
                 detection_status='UNKNOWN', measurements=None, failed_specs=None,
                 mt0_path='', log_path='', sim_time_s=0.0, error_message=''):
        self.run_id = run_id
        self.fault_id = fault_id
        self.corner = corner
        self.simulation_status = simulation_status
        self.detection_status = detection_status
        self.measurements = measurements or {}
        self.failed_specs = failed_specs or []
        self.mt0_path = mt0_path
        self.log_path = log_path
        self.sim_time_s = float(sim_time_s)
        self.error_message = error_message

    def to_dict(self):
        return {
            'run_id': self.run_id, 'fault_id': self.fault_id,
            'corner': self.corner, 'simulation_status': self.simulation_status,
            'detection_status': self.detection_status,
            'failed_specs': ','.join(self.failed_specs),
            'mt0_path': self.mt0_path, 'log_path': self.log_path,
            'sim_time_s': self.sim_time_s, 'error_message': self.error_message
        }
