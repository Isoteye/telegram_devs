from database.models import Developer, User, DeveloperStatus, Order, OrderStatus, DeveloperRequest, RequestStatus
from typing import List, Optional, Tuple
import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

class DeveloperService:
    def __init__(self, db_session):
        self.db = db_session
    
    def generate_developer_id(self) -> str:
        """Generate unique developer ID"""
        last_dev = self.db.query(Developer).order_by(Developer.id.desc()).first()
        next_num = 1 if not last_dev else last_dev.id + 1
        return f"DEV{next_num:03d}"
    
    def register_developer(self, telegram_user, skills: str = "", experience: str = "", hourly_rate: float = None) -> Tuple[Developer, bool]:
        """Register a new developer"""
        try:
            # First get or create the user
            user = self.db.query(User).filter(User.telegram_id == telegram_user.id).first()
            
            if not user:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    is_developer=False
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
            
            # Check if already a developer
            existing_dev = self.db.query(Developer).filter(Developer.user_id == user.id).first()
            if existing_dev:
                logger.info(f"Developer already exists: {existing_dev.developer_id}")
                return existing_dev, False
            
            # Create developer
            developer_id = self.generate_developer_id()
            developer = Developer(
                user_id=user.id,
                developer_id=developer_id,
                skills=skills,
                experience=experience,
                hourly_rate=hourly_rate,
                status=DeveloperStatus.ACTIVE,
                is_available=True,
                completed_orders=0,
                rating=0.0,
                earnings=0.0
            )
            
            self.db.add(developer)
            
            # Update user to mark as developer
            user.is_developer = True
            self.db.commit()
            self.db.refresh(developer)
            
            logger.info(f"✅ Registered new developer: {developer.developer_id}")
            return developer, True
            
        except IntegrityError as e:
            logger.error(f"Integrity error registering developer: {e}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Error registering developer: {e}")
            self.db.rollback()
            raise
    
    def submit_developer_application(self, user_id: int, skills: str, experience: str, 
                                   portfolio_url: str = None, github_url: str = None, 
                                   hourly_rate: float = 25.0) -> DeveloperRequest:
        """Submit a developer application"""
        try:
            # Check for existing pending application
            existing_request = self.db.query(DeveloperRequest).filter(
                DeveloperRequest.user_id == user_id,
                DeveloperRequest.status == RequestStatus.NEW
            ).first()
            
            if existing_request:
                return existing_request
            
            # Create new application
            request = DeveloperRequest(
                user_id=user_id,
                skills_experience=f"Skills: {skills}\nExperience: {experience}",
                portfolio_url=portfolio_url,
                github_url=github_url,
                hourly_rate=hourly_rate,
                status=RequestStatus.NEW
            )
            
            self.db.add(request)
            self.db.commit()
            self.db.refresh(request)
            
            logger.info(f"Developer application submitted by user {user_id}")
            return request
            
        except Exception as e:
            logger.error(f"Error submitting developer application: {e}")
            self.db.rollback()
            raise
    
    def get_developer(self, developer_id: str) -> Optional[Developer]:
        """Get developer by ID"""
        try:
            return self.db.query(Developer).filter(Developer.developer_id == developer_id).first()
        except Exception as e:
            logger.error(f"Error getting developer: {e}")
            return None
    
    def get_developer_by_user(self, telegram_id: int) -> Optional[Developer]:
        """Get developer by telegram user ID"""
        try:
            user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None
            return self.db.query(Developer).filter(Developer.user_id == user.id).first()
        except Exception as e:
            logger.error(f"Error getting developer by user: {e}")
            return None
    
    def get_all_developers(self) -> List[Developer]:
        """Get all developers"""
        try:
            return self.db.query(Developer).order_by(Developer.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting all developers: {e}")
            return []
    
    def get_available_developers(self) -> List[Developer]:
        """Get available developers"""
        try:
            return self.db.query(Developer).filter(
                Developer.is_available == True,
                Developer.status == DeveloperStatus.ACTIVE
            ).order_by(Developer.rating.desc()).all()
        except Exception as e:
            logger.error(f"Error getting available developers: {e}")
            return []
    
    def update_developer_status(self, developer_id: str, status: DeveloperStatus, is_available: bool = None) -> bool:
        """Update developer status"""
        try:
            developer = self.get_developer(developer_id)
            if not developer:
                return False
            
            developer.status = status
            if is_available is not None:
                developer.is_available = is_available
            
            self.db.commit()
            logger.info(f"Updated developer {developer_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating developer status: {e}")
            self.db.rollback()
            return False
    
    def assign_order_to_developer(self, order_id: str, developer_id: str) -> Tuple[bool, str]:
        """Assign order to developer"""
        try:
            order = self.db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                return False, "Order not found"
            
            # Check if order is approved and available for assignment
            if order.status != OrderStatus.APPROVED:
                return False, f"Order status is {order.status.value}, must be 'approved'"
            
            developer = self.get_developer(developer_id)
            if not developer:
                return False, "Developer not found"
            
            # Check if developer is available
            if not developer.is_available or developer.status != DeveloperStatus.ACTIVE:
                return False, "Developer is not available"
            
            # Assign order
            order.assigned_developer_id = developer.id
            order.status = OrderStatus.ASSIGNED
            
            # Update developer status
            developer.is_available = False
            
            self.db.commit()
            
            logger.info(f"✅ Order {order_id} assigned to developer {developer_id}")
            return True, "Order assigned successfully"
            
        except Exception as e:
            logger.error(f"Error assigning order to developer: {e}")
            self.db.rollback()
            return False, str(e)
    
    def complete_order(self, order_id: str, developer_notes: str = None) -> bool:
        """Mark order as completed by developer"""
        try:
            order = self.db.query(Order).filter(Order.order_id == order_id).first()
            if not order or not order.assigned_developer_id:
                return False
            
            developer = self.db.query(Developer).filter(Developer.id == order.assigned_developer_id).first()
            if not developer:
                return False
            
            # Update order
            order.status = OrderStatus.COMPLETED
            if developer_notes:
                order.developer_notes = developer_notes
            
            # Update developer
            developer.is_available = True
            developer.completed_orders += 1
            
            self.db.commit()
            logger.info(f"Order {order_id} completed by developer {developer.developer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing order: {e}")
            self.db.rollback()
            return False
    
    def get_developer_orders(self, developer_id: str) -> List[Order]:
        """Get orders assigned to a developer"""
        try:
            developer = self.get_developer(developer_id)
            if not developer:
                return []
            
            return self.db.query(Order).filter(
                Order.assigned_developer_id == developer.id
            ).order_by(Order.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting developer orders: {e}")
            return []
    
    def update_developer_info(self, developer_id: str, skills: str = None, experience: str = None, hourly_rate: float = None) -> bool:
        """Update developer information"""
        try:
            developer = self.get_developer(developer_id)
            if not developer:
                return False
            
            if skills is not None:
                developer.skills = skills
            if experience is not None:
                developer.experience = experience
            if hourly_rate is not None:
                developer.hourly_rate = hourly_rate
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating developer info: {e}")
            self.db.rollback()
            return False
    
    def get_pending_applications(self) -> List[DeveloperRequest]:
        """Get all pending developer applications"""
        try:
            return self.db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.NEW
            ).order_by(DeveloperRequest.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting pending applications: {e}")
            return []
    
    def approve_developer_application(self, request_id: int, admin_id: int) -> Tuple[bool, str, Optional[Developer]]:
        """Approve a developer application and create developer account"""
        try:
            # Get the application
            dev_request = self.db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            if not dev_request:
                return False, "Application not found", None
            
            if dev_request.status != RequestStatus.NEW:
                return False, f"Application status is {dev_request.status.value}, not new", None
            
            user = self.db.query(User).filter(User.id == dev_request.user_id).first()
            if not user:
                return False, "User not found", None
            
            if user.is_developer:
                return False, "User is already a developer", None
            
            # Generate developer ID
            developer_id = self.generate_developer_id()
            
            # Create developer
            developer = Developer(
                user_id=user.id,
                developer_id=developer_id,
                status=DeveloperStatus.ACTIVE,
                is_available=True,
                skills=dev_request.skills_experience,
                hourly_rate=dev_request.hourly_rate or 25.0,
                portfolio_url=dev_request.portfolio_url,
                github_url=dev_request.github_url,
                completed_orders=0,
                rating=0.0,
                earnings=0.0
            )
            
            # Update user and request
            user.is_developer = True
            dev_request.status = RequestStatus.APPROVED
            
            self.db.add(developer)
            self.db.commit()
            self.db.refresh(developer)
            
            logger.info(f"✅ Developer application approved: {developer_id}")
            return True, f"Developer {developer_id} created successfully", developer
            
        except Exception as e:
            logger.error(f"Error approving developer application: {e}")
            self.db.rollback()
            return False, str(e), None
    
    def reject_developer_application(self, request_id: int, reason: str = None) -> Tuple[bool, str]:
        """Reject a developer application"""
        try:
            dev_request = self.db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            if not dev_request:
                return False, "Application not found"
            
            if dev_request.status != RequestStatus.NEW:
                return False, f"Application status is {dev_request.status.value}, not new"
            
            dev_request.status = RequestStatus.REJECTED
            if reason:
                dev_request.admin_notes = f"Rejected: {reason}"
            
            self.db.commit()
            logger.info(f"Developer application {request_id} rejected")
            return True, "Application rejected"
            
        except Exception as e:
            logger.error(f"Error rejecting developer application: {e}")
            self.db.rollback()
            return False, str(e)