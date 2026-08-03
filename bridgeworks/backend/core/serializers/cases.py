from rest_framework import serializers
from core.models import CaseFile, IssueComment, CaseFileImage
from .orders import SimpleOrderForCaseFileSerializer


class CaseFileImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseFileImage
        fields = ['id', 'image', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class IssueCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = IssueComment
        fields = [
            'id', 'case', 'user', 'user_name', 'message', 
            'is_internal_note', 'created_at'
        ]
        read_only_fields = ['user', 'created_at', 'case']
        
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class CaseFileSerializer(serializers.ModelSerializer):
    registered_by_name = serializers.CharField(source='registered_by.username', read_only=True)
    order_details = SimpleOrderForCaseFileSerializer(source='order', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    
    images = CaseFileImageSerializer(many=True, read_only=True)
    latest_update = serializers.SerializerMethodField()
    resolution_time = serializers.SerializerMethodField()
    history = IssueCommentSerializer(source='comments', many=True, read_only=True)
    
    class Meta:
        model = CaseFile
        fields = [
            'id', 'case_number', 'order', 'order_details', 'subject', 'description', 
            'issue_type', 'type_display', 'status', 'status_display', 'priority', 
            'registered_by', 'registered_by_name', 
            'created_at', 'updated_at', 'first_place_of_contact',
            'latest_remark',
            'solution_provided_text',
            'reshipment_order_number', 
            'images', 
            'latest_update',
            'history', 'resolution_time', 'resolved_at'
        ]
        read_only_fields = [
            'case_number', 'registered_by', 'created_at', 'order_details', 
            'registered_by_name', 'status_display', 'type_display',
            'images', 'history', 'latest_update'
        ]
        
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['registered_by'] = user
        images_data = self.context['request'].FILES.getlist('images')
        
        case = super().create(validated_data)
        
        if images_data:
            for image_file in images_data:
                CaseFileImage.objects.create(case=case, image=image_file)
        
        IssueComment.objects.create(
            case=case, 
            user=user, 
            message=f"Case File Created via {validated_data.get('first_place_of_contact', 'Web')}",
            is_internal_note=True
        )
        return case

    def update(self, instance, validated_data):
        user = self.context['request'].user
        changes_log = []

        if 'status' in validated_data and validated_data['status'] != instance.status:
            old_status = instance.get_status_display()
            instance.status = validated_data['status'] 
            new_status = instance.get_status_display()
            changes_log.append(f"Status: {old_status} ➝ {new_status}")

        new_solution = validated_data.get('solution_provided_text')
        if new_solution is not None and new_solution != instance.solution_provided_text:
            if new_solution.strip():
                changes_log.append(f"Solution: '{new_solution}'")
            else:
                changes_log.append("Solution cleared")

        new_reshipment = validated_data.get('reshipment_order_number')
        if new_reshipment is not None and new_reshipment != instance.reshipment_order_number:
            if new_reshipment.strip():
                changes_log.append(f"Reshipment Order: #{new_reshipment}")
            else:
                changes_log.append("Reshipment Order removed")

        instance = super().update(instance, validated_data)

        images_data = self.context['request'].FILES.getlist('images')
        if images_data:
            for image_file in images_data:
                CaseFileImage.objects.create(case=instance, image=image_file)
            changes_log.append(f"Added {len(images_data)} new image(s)")

        manual_remark = validated_data.get('latest_remark', '').strip()
        full_log_message = ""
        
        if manual_remark:
            full_log_message += f"{manual_remark}" 
        
        if changes_log:
            system_msg = f"(System: {', '.join(changes_log)})"
            if full_log_message:
                full_log_message += f"\n{system_msg}"
            else:
                full_log_message = system_msg

        if full_log_message:
            IssueComment.objects.create(
                case=instance,
                user=user,
                message=full_log_message.strip(),
                is_internal_note=True
            )

        return instance
    
    def get_latest_update(self, obj):
        latest_comment = obj.comments.order_by('-created_at').first()
        if latest_comment:
            return {
                "user": latest_comment.user.username,
                "message": latest_comment.message,
                "created_at": latest_comment.created_at.isoformat(),
            }
        
        return {
            "user": obj.registered_by.username,
            "message": "FIR Filed",
            "created_at": obj.created_at.isoformat(),
        }
        
    def get_resolution_time(self, obj):
        if not obj.resolved_at:
            return "Pending"
        
        diff = obj.resolved_at - obj.created_at
        days = diff.days
        seconds = diff.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
